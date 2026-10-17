"""약물·보충제 확인 (D10, D11, D12). 판정은 조회표가 하고 LLM은 설명만 한다.

조회표: knowledge/drugs/curated/substances.json(성분, 손으로 정리), knowledge/drugs/curated/products.json(제품·제품군),
knowledge/drugs/wada/processed/prohibited_list_<연도>.json(WADA 금지목록 PDF 자동 추출, analysis/wada_extract.py),
knowledge/drugs/kr_source/processed/kr_products.json.gz(한글 제품명 → 영문 성분명, 심평원 약가마스터, analysis/kr_drug_names.py).
찾는 순서: 손 조회표의 성분 → 손 조회표의 제품군 → 한글 제품명(약가마스터) → 손 조회표의 제품 → WADA 추출본 →
한글 성분명(약가마스터 제품명 안에 들어 있는 경우) → 부분 일치(판정 없이 주의 성분만).
- 한글 제품명은 정확히 일치 → 앞부분 일치. 후보들의 성분 구성이 서로 다르면 판정하지 않는다(category + 후보 목록).
  성분 정보가 없는 제품(두 원본의 갱신 시점 차이)은 UNKNOWN이지 NOT_LISTED_VERIFY가 아니다.
- 제품의 영문 성분명은 염·수화물 표기를 떼고 손 조회표 → WADA 순으로 찾고, 없으면 금지 이름(6자 이상)이
  성분명 안에 들어 있는지 본다(가장 긴 것, 성분명 ⊇ 금지 이름 방향만). S9 당질코르티코이드와 흡입 β2 예외는
  제품의 투여 경로로 판정을 바꾼다.
- "허용" 상태는 없다. 목록에 없는 성분도 NOT_LISTED_VERIFY(확인 필요)다.
- 제품군(category)은 성분을 특정할 수 없으므로 항상 UNKNOWN이고, 성분 목록은 '주의 성분'이다.
- WADA 추출 항목의 예외(용량·경로·용도 조건)는 조건 충족 여부를 알 수 없으므로 CONDITIONAL + 조건 안내.
  조건 없이 "금지 아님"인 항목(모니터링 대상 등)만 NOT_LISTED_VERIFY.
- 사용 시기는 상태를 낮추지 않는다. 경기기간 중에만 금지인 성분을 경기기간 외에 쓴다고 해도
  상태는 그대로 두고, 절차에서 경기 전 잔류 가능성을 안내한다(D11 "모름 = 경기기간 중"의 연장).
"""

import bisect
import json
import re
from datetime import date
from functools import cache

from app.drugs import drug_db
from app.config import DEMO_MODE, DRUGS
from app.schemas import (CheckResult, CheckStatus, CountryRoute, DataSource, Ingredient, OfficialLink, ProductCandidate,
                         Timing)

STRICTNESS: list[CheckStatus] = ["PROHIBITED", "IN_COMPETITION_ONLY", "THRESHOLD", "CONDITIONAL", "NOT_LISTED_VERIFY",
                                  "UNKNOWN"]
FLAGGED: tuple[CheckStatus, ...] = ("PROHIBITED", "IN_COMPETITION_ONLY", "THRESHOLD", "CONDITIONAL")


@cache
def _store() -> dict:
    """약물 DB(var/drugs.sqlite). 원천 JSON과 다르면 데모에서는 다시 빌드, 시범에서는 거부(drug_db.ensure)."""
    drug_db.ensure(DEMO_MODE)
    return drug_db.load()


def _load(name: str) -> dict:
    return json.loads((DRUGS / "curated" / name).read_text(encoding="utf-8"))


# WADA 원문은 그리스 문자와 비슷한 글자를 섞어 쓴다(예: "ɑ-PVP", "3ß-hydroxy…"의 ß는 β 자리).
GREEK = str.maketrans({"α": "a", "ɑ": "a", "β": "b", "ß": "b", "\u200b": "", "\ufeff": ""})


# 영국식·INN 표기 차이 중 실제로 매칭을 깨던 것만(약가마스터 "beclomethasone" ↔ WADA "beclometasone").
SPELLING = [("methasone", "metasone")]


def normalize(text: str) -> str:
    s = re.sub(r"[\s\-_·()（）\[\]]", "", text.translate(GREEK)).lower()
    for a, b in SPELLING:
        s = s.replace(a, b)
    return s


def name_variants(name: str) -> list[str]:
    """이름 전체, 괄호 앞부분, 괄호 안의 이름. "enobosarm (ostarine)" → 전체, enobosarm, ostarine.
    이름 전체는 항상 색인하고, 괄호에서 떼어 낸 조각은 너무 짧으면("(d-)" 등) 뺀다(한글은 두 글자부터)."""
    fragments = [re.split(r"[(（]", name)[0], *re.findall(r"[(（]([^)）]+)[)）]", name)]
    keep = [normalize(f) for f in fragments]
    keep = [k for k in keep if len(k) > 2 or (len(k) == 2 and re.search(r"[가-힣]", k))]
    return list(dict.fromkeys([normalize(name), *keep]))


EXCEPTION_NOTE = "조건(용량·투여 경로·용도)에 따라 금지되지 않을 수 있어요."
P1_NOTE = "베타차단제는 지정 종목에서만 금지되며 역도는 해당하지 않아요(다른 종목은 확인 필요)."


@cache
def _wada() -> tuple[dict, dict[str, list[dict]]]:
    """WADA 추출본과 이름 색인(정규화한 이름·동의어 → 항목들). 같은 이름이 금지와 예외로 함께 나올 수 있다."""
    wada = _store()["wada"]
    if "weightlifting" in {x.lower() for x in wada["sections"]["P1"].get("sports", [])}:
        raise RuntimeError("P1 종목에 역도가 있음 — P1 규칙(NOT_LISTED_VERIFY)을 다시 정해야 함")
    index: dict[str, list[dict]] = {}
    for item in wada["items"]:
        for name in [item["name"], *item.get("synonyms", []), *item.get("aliases", [])]:
            for key in name_variants(name):
                if item not in index.setdefault(key, []):
                    index[key].append(item)
    return wada, index


def _wada_ingredient(items: list[dict]) -> Ingredient:
    """추출 항목(들) → 상태. 우선순위: 예외 > 기준치 > 금지 구분(prohibited 필드)."""
    wada, _ = _wada()
    first = items[0]
    kinds = {i["kind"] for i in items}
    # 조건으로 보여줄 원문: 예외·기준치, 또는 각주가 달린 금지 항목(예: 에피네프린 국소 사용). 일반 금지 항목의
    # condition은 나열 줄 발췌일 뿐이라 보여주지 않는다.
    conditions = [i["condition"] for i in items
                  if i.get("condition") and (i["kind"] != "prohibited" or i.get("footnote_stars"))]
    section = first["section"]
    note = None
    if "exception" in kinds:
        if all(i["prohibited"] == "no" for i in items):
            status: CheckStatus = "NOT_LISTED_VERIFY"
            note = "금지목록에 '금지 아님'으로 명시된 성분이에요(모니터링 대상 등)."
        else:
            status, note = "CONDITIONAL", EXCEPTION_NOTE
    elif "threshold" in kinds:
        status = "THRESHOLD"
    elif first["prohibited"] == "all_times":
        status = "PROHIBITED"
    elif first["prohibited"] == "in_competition":
        status = "IN_COMPETITION_ONLY"
    else:  # particular_sports(P1) 또는 no
        status, note = "NOT_LISTED_VERIFY", P1_NOTE if section == "P1" else None
    extra = wada["section_conditions"].get(section) if section in ("S3", "S9") else None
    parts = [x for x in [note, extra, *(f"원문: {c}" for c in conditions[:2])] if x]
    return Ingredient(name_ko=first["name"], name_en=first["name"], status=status,
                      wada_class=first.get("subsection") or section, note=" ".join(parts) or None,
                      source_url=wada["source_url"])


@cache
def _tables() -> tuple[dict, dict, dict, dict]:
    substances, products = _store()["substances"], _store()["products"]
    dro: dict = {}  # (예전 국가 경로 설정 — 확인처 안내를 빼면서 파일 삭제)
    index: dict[str, tuple[str, str]] = {}
    for sid, s in substances["substances"].items():
        for name in [s["name_ko"], s["name_en"], *s.get("aliases", [])]:
            for key in name_variants(name):
                index[key] = ("substance", sid)
    # 제품 이름이 성분 이름과 겹치면 제품을 우선한다(제품에는 보충제 경고 등 정보가 더 있음)
    for pid, p in products["products"].items():
        for name in [pid, *p.get("aliases", [])]:
            index[normalize(name)] = ("product", pid)
    return substances, products, dro, index


def _match(query: str) -> tuple[str, str] | None:
    """정확히 일치하면 ("substance"|"product", id). 이름이 일부만 들어 있으면 ("partial", ...)로 따로 처리한다."""
    _, _, _, index = _tables()
    return index.get(normalize(query))


def _partial(query: str) -> list[str]:
    """'타이레놀 콜드', '슈도에페드린 시럽'처럼 이름이 섞인 입력. 다른 성분이 더 있을 수 있으므로
    판정하지 않고 주의 성분만 모은다(가장 보수적인 처리)."""
    substances, products, _, index = _tables()
    q = normalize(query)
    ids: list[str] = []
    for name, (kind, key) in index.items():
        if len(name) >= 2 and name in q:
            for sid in ([key] if kind == "substance" else products["products"][key]["ingredients"]):
                if sid not in ids and substances["substances"][sid]["status"] != "NOT_LISTED_VERIFY":
                    ids.append(sid)
    return ids


def _ingredient(sid: str) -> tuple[Ingredient, bool]:
    s = _tables()[0]["substances"][sid]
    return Ingredient(name_ko=s["name_ko"], name_en=s["name_en"], status=s["status"], wada_class=s.get("wada_class"),
                      note=s.get("note"), source_url=s["source_url"]), s["reviewed"]


# ---------- 한글 제품명 (심평원 약가마스터) ----------

HIRA_URL = "https://www.data.go.kr/data/15067462/fileData.do"
NO_MATCH_NOTE = "금지목록의 이름과 일치하는 항목이 없어요. 목록 이름과 표기가 다를 수 있으니 확인하세요."
SALT = re.compile(r"\b(hydrochloride|hcl|hydrobromide|hemisulfate|sulfate|sulphate|maleate|citrate|bitartrate|tartrate|"
                  r"phosphate|disodium|sodium|potassium|calcium|magnesium|hemisuccinate|succinate|acetate|dipropionate|"
                  r"propionate|valerate|butyrate|furoate|acetonide|mesylate|mesilate|besylate|besilate|fumarate|"
                  r"monohydrate|dihydrate|trihydrate|hydrate|anhydrous|micronized|base|bromide|chloride|nitrate|"
                  r"lactate|gluconate|palmitate)\b")
INHALED_EXCEPTIONS = ("salbutamol", "formoterol", "salmeterol", "vilanterol")
# 금지목록은 계열 전체를 금지하면서 이름은 일부만 예로 든다("and other substances with a similar…").
# 성분 이름이 어느 목록과도 맞지 않을 때만, 제품의 ATC 약효 분류로 같은 계열의 기준을 적용한다.
# S9는 상태를 경기기간 중 금지로 두고 by_route가 투여 경로로 다시 정한다(외용 → 조건부).
# 계열 전체가 금지인 것만 넣는다(S9 "모든 당질코르티코이드", S5 "이뇨제", S3 "β2 작용제", S1 단백동화제).
# S6 흥분제는 "이름 + 비슷한 구조"라 ATC 계열(N06BA)에 금지가 아닌 약(atomoxetine 등)이 섞여 있어, 판정 대신
# UNKNOWN + 전문가 확인으로 둔다.
ATC_CLASSES: list[tuple[str, CheckStatus, str]] = [
    *[(p, "IN_COMPETITION_ONLY", "S9") for p in ("H02", "D07", "S01B", "S01C", "S02B", "S02C", "S03B", "S03C",
                                               "R01AD", "R03BA", "A07EA", "C05AA", "D10AA")],
    ("C03", "PROHIBITED", "S5"),
    ("A14A", "PROHIBITED", "S1"),
    ("R03AC", "PROHIBITED", "S3"),
    ("R03CC", "PROHIBITED", "S3"),
    ("N06BA", "UNKNOWN", "S6"),
]
ATC_UNKNOWN_NOTE = ("같은 약효 계열(ATC {atc})에 경기기간 중 금지 흥분제가 있지만, 계열 전체가 금지는 아니에요. "
                    "")
MAX_CANDIDATES = 10


def clean_english(name: str) -> str:
    """약가마스터 영문 일반명 → 목록 이름에 맞추기: "(as …)", "dl-/d-/l-" 접두, 염·수화물 단어를 뗀다."""
    s = re.sub(r"\(as [^)]*\)", " ", name.lower())
    s = re.sub(r"(?<![a-z])(dl|d|l)-", "", s)
    return re.sub(r"\s+", " ", SALT.sub(" ", s)).strip()


@cache
def _substring_keys() -> list[tuple[str, tuple[str, str]]]:
    """부분 일치용 이름(영문, 6자 이상), 긴 것부터. 손 조회표가 같은 이름을 가지면 손 조회표."""
    keys: dict[str, tuple[str, str]] = {}
    for k, (kind, sid) in _tables()[3].items():
        if kind == "substance" and k.isascii() and len(k) >= 6:
            keys[k] = ("hand", sid)
    for k in _wada()[1]:
        if k.isascii() and len(k) >= 6:
            keys.setdefault(k, ("wada", k))
    return sorted(keys.items(), key=lambda kv: -len(kv[0]))


@cache
def resolve_english(name: str) -> Ingredient:
    """제품의 영문 성분명 하나 → 성분 상태. 화면에는 약가마스터의 원래 이름을 name_en으로 보여준다."""
    hand, wada = _tables()[3], _wada()[1]
    # 원래 이름("triamcinolone acetonide"는 WADA에 이 이름 그대로 있음)을 먼저, 그다음 염을 뗀 이름으로 찾는다
    keys = [k for k in dict.fromkeys([normalize(re.sub(r"\(as [^)]*\)", "", name)), normalize(clean_english(name))]) if k]
    hand_key = next((k for k in keys if hand.get(k, ("",))[0] == "substance"), None)
    wada_key = next((k for k in keys if k in wada), None)
    if hand_key:
        ing = _ingredient(hand[hand_key][1])[0]
    elif wada_key:
        ing = _wada_ingredient(wada[wada_key])
    else:
        hit = next((v for k, v in _substring_keys() if any(k in key for key in keys)), None)
        if hit is None:
            return Ingredient(name_ko=name, name_en=name, status="NOT_LISTED_VERIFY", note=NO_MATCH_NOTE,
                              source_url=HIRA_URL)
        ing = _ingredient(hit[1])[0] if hit[0] == "hand" else _wada_ingredient(wada[hit[1]])
    return ing.model_copy(update={"name_en": name})


def by_atc(ing: Ingredient, atc: str) -> Ingredient:
    """이름이 어느 목록에도 없을 때만: 제품의 ATC가 금지 계열이면 그 계열의 기준을 적용한다(엄격한 쪽)."""
    if ing.note != NO_MATCH_NOTE or not atc:
        return ing
    hit = next(((status, cls) for prefix, status, cls in ATC_CLASSES if atc.startswith(prefix)), None)
    if hit is None:
        return ing
    note = ATC_UNKNOWN_NOTE.format(atc=atc) if hit[0] == "UNKNOWN" else \
        f"금지목록에 이름은 없지만 같은 약효 계열(ATC {atc})이라 그 계열의 기준으로 판단했어요. 확인하세요."
    return ing.model_copy(update={"status": hit[0], "wada_class": hit[1], "note": note})


def by_route(ing: Ingredient, route: str, form: str) -> Ingredient:
    """제품 데이터만이 주는 정보: 투여 경로. S9는 경구·주사·직장이면 경기기간 중 금지, 외용이면 조건부.
    흡입 β2 예외 성분(살부타몰 등)은 흡입이 아니면 예외에 해당하지 않는다. 경로를 모르면 그대로(엄격한 쪽)."""
    cls = ing.wada_class or ""
    rectal = any(x in form for x in ("좌", "관장"))
    atc_note = f" {ing.note}" if ing.note and "ATC" in ing.note else ""  # 계열로 판단한 사실은 남긴다
    if cls.startswith("S9"):
        if route in ("내복", "주사") or rectal:
            return ing.model_copy(update={"status": "IN_COMPETITION_ONLY",
                                          "note": "경구·주사·직장 투여 제형이라 경기기간 중 금지 대상이에요." + atc_note})
        if route == "외용":
            return ing.model_copy(update={"status": "CONDITIONAL",
                                          "note": "외용 제형(국소·흡입 등)은 허가 용량 안에서 금지되지 않아요. "
                                                  "" + atc_note})
    if cls.startswith("S3") and any(x in normalize(ing.name_en) for x in INHALED_EXCEPTIONS):
        if route in ("내복", "주사"):
            return ing.model_copy(update={"status": "PROHIBITED",
                                          "note": "흡입이 아닌 경로(먹는 약·주사)는 흡입 용량 예외에 해당하지 않아요."})
    return ing


@cache
def _kr() -> tuple[dict, dict[str, list[list]], list[str]]:
    data = _store()["kr"]
    index: dict[str, list[list]] = {}
    for row in data["products"]:
        index.setdefault(normalize(row[0]), []).append(row)
    return data, index, sorted(index)


def _kr_candidates(query: str) -> list[list]:
    """정확히 일치하는 제품명, 없으면 그 이름으로 시작하는 제품명들."""
    _, index, keys = _kr()
    q = normalize(query)
    if len(q) < 2:
        return []
    if q in index:
        return index[q]
    out, i = [], bisect.bisect_left(keys, q)
    while i < len(keys) and keys[i].startswith(q):
        out += index[keys[i]]
        i += 1
    return out


def _kr_data_source() -> DataSource:
    meta = _kr()[0]["meta"]
    date_ = next(s["date"] for s in meta["sources"] if s["url"] == HIRA_URL)
    return DataSource(label=f"건강보험심사평가원 약가마스터({meta['license']}, {date_} 기준)", url=HIRA_URL)


@cache
def _kr_ingredients(group_code: str, atc: str) -> tuple[Ingredient, ...] | None:
    """제품 한 줄의 성분 판정(이름 → ATC 계열 → 투여 경로). 성분 정보가 없으면 None."""
    data = _kr()[0]
    group = data["groups"].get(group_code)
    if group is None:
        return None
    out: dict[tuple[str, str], Ingredient] = {}
    for i, route, form in group:
        ing = by_route(by_atc(resolve_english(data["ingredients"][i]), atc), route, form)
        out.setdefault((ing.name_en, ing.status), ing)
    return tuple(out.values())


def _kr_lookup(query: str) -> dict | None:
    """제품 검색 결과를 check()가 쓰는 조각으로. 후보가 없으면 None.
    후보들을 '판정 결과'(성분 이름·상태)로 묶어, 모두 같으면 제품으로 판정하고(정제·주사처럼 제형만 다른 경우),
    다르면 판정하지 않는다."""
    cands = _kr_candidates(query)
    if not cands:
        return None
    groups: dict[tuple | None, list[tuple[list, tuple[Ingredient, ...] | None]]] = {}
    for row in cands:
        ings = _kr_ingredients(row[3], row[4])
        key = None if ings is None else tuple(sorted((i.name_en, i.status) for i in ings))
        groups.setdefault(key, []).append((row, ings))

    if len(groups) == 1:
        key, members = next(iter(groups.items()))
        if key is None:
            return dict(kind="product", ingredients=[], status="UNKNOWN",
                        note="제품은 찾았지만 성분 정보를 찾지 못했어요. 포장의 성분명으로 다시 검색하세요.")
        ings = list(members[0][1])
        return dict(kind="product", ingredients=ings, status=min((i.status for i in ings), key=STRICTNESS.index),
                    note=None)

    flagged: dict[str, Ingredient] = {}
    candidates = []
    for _, members in sorted(groups.items(), key=lambda kv: kv[1][0][0][0]):
        row, ings = members[0]
        for ing in ings or ():
            if ing.status in FLAGGED:
                flagged.setdefault(ing.name_en, ing)
        if len(candidates) < MAX_CANDIDATES:
            candidates.append(ProductCandidate(name=row[0], otc=row[2], ingredients=[i.name_en for i in ings or ()]))
    note = "이 이름으로 시작하는 제품이 여러 개이고 판정이 서로 달라요. 포장에 적힌 제품명 전체로 다시 검색하세요."
    if None in groups:
        note += " 성분 정보를 찾지 못한 제품도 있어요."
    return dict(kind="category", ingredients=list(flagged.values()), status="UNKNOWN", note=note,
                candidates=candidates)


KR_NAME_NOTE = ("한글 성분명을 약가마스터 제품명 {n}개에서 찾아 영문 성분명({en})에 연결했어요. "
                "투여 경로(먹는 약·주사·바르는 약)에 따라 기준이 달라질 수 있으니 제품명으로도 확인하세요.")


def _kr_by_ingredient_name(query: str) -> dict | None:
    """'펜터민', '모메타손'처럼 한글 성분명만 입력한 경우. 약가마스터에는 한글 성분명 열이 없지만 복제약 제품명에
    성분명이 들어 있다("○○펜터민정"). 이름이 들어간 **단일 성분** 제품들이 모두 같은 성분(염 표기 제외)일 때만
    그 성분으로 판정하고, 상태는 제품들 가운데 가장 엄격한 것. 성분이 둘 이상 섞이면 판정하지 않는다(None) —
    '펜타닐'은 레미펜타닐 제품에도, '에피네프린'은 노르에피네프린 제품에도 들어 있어서 여기서 걸러진다."""
    q = normalize(query)
    if len(q) < 3 or not re.fullmatch(r"[가-힣]+", q):
        return None
    data, index, keys = _kr()
    found: dict[str, list[Ingredient]] = {}
    n = 0
    for key in keys:
        if q not in key:
            continue
        for _, _, _, group_code, atc in index[key]:
            group = data["groups"].get(group_code)
            if not group or len({i for i, _, _ in group}) != 1:
                continue
            raw = data["ingredients"][group[0][0]]
            base = re.sub(r"\(.*", "", clean_english(raw)).split()[0]  # 에스터("… aceponate")·농도 표기는 같은 성분으로
            found.setdefault(base, []).append(by_atc(resolve_english(raw), atc))
            n += 1
    if len(found) != 1:
        return None
    en, ings = next(iter(found.items()))
    ing = min(ings, key=lambda i: STRICTNESS.index(i.status))
    return dict(kind="substance", ingredients=[ing.model_copy(update={"name_ko": query.strip(), "name_en": en})],
                status=ing.status, note=KR_NAME_NOTE.format(n=n, en=en))


def _route(country: str) -> CountryRoute:
    return "kada" if country == "KR" else "local_unverified"


def _links(route: CountryRoute, status: CheckStatus, extra: list[dict]) -> list[OfficialLink]:
    """다른 기관에서 다시 확인하라는 링크는 붙이지 않는다(2026-10-17 사용자). 제품 표에 적힌 링크만 그대로."""
    return [OfficialLink(**e) for e in extra]


def _steps(status: CheckStatus, kind: str, route: CountryRoute, timing: Timing, supplement: bool,
           note: str | None) -> list[str]:
    steps: list[str] = []
    if kind in ("category", "unmatched"):
        steps.append("제품 포장이나 설명서에서 성분명을 확인하고, 성분명으로 다시 검색하세요.")
    if kind == "unmatched":
        steps.append("의약품 목록에서 찾지 못했어요. 보충제(건강기능식품)나 해외 제품이면 성분표의 성분명으로 다시 검색하세요.")
    if note:
        steps.append(note)
    if status == "PROHIBITED":
        steps.append("경기기간과 관계없이 항상 금지된 성분이에요.")
    elif status == "IN_COMPETITION_ONLY":
        steps.append("경기기간 중 금지된 성분이에요.")
    elif status == "THRESHOLD":
        steps.append("정해진 용량이나 소변 농도 기준을 넘으면 위반이에요. 복용량과 시점에 따라 달라져요.")
    elif status == "CONDITIONAL":
        steps.append("조건(용량·투여 경로·용도)을 지키면 금지되지 않는 성분이에요.")
    elif status == "NOT_LISTED_VERIFY":
        steps.append("금지목록에서 확인되지 않았어요.")
    if status in ("IN_COMPETITION_ONLY", "THRESHOLD") and timing == "out_of_competition":
        steps.append("경기기간 전에 복용해도 경기 때까지 몸에 남아 검출될 수 있어요.")
    if timing == "unknown":
        steps.append("사용 시기를 모르면 경기기간 중 기준으로 판단했어요.")
    if supplement:
        steps.append("보충제는 성분표에 없는 금지물질이 섞여 있을 수 있어요. 성분이 문제없어 보여도 위험이 남아요.")
    if route != "kada":
        steps.append("해외 제품은 같은 이름이라도 국내 제품과 성분이 다를 수 있어요.")
    return steps


def check(query: str, country: str, timing: Timing) -> CheckResult:
    substances, products, _, _ = _tables()
    country = country.upper()
    route = _route(country)
    hit = _match(query)
    hand_product = products["products"][hit[1]] if hit and hit[0] == "product" else None

    kind, supplement, reviewed, note, extra = "unmatched", False, False, None, []
    candidates: list[ProductCandidate] = []
    sources: list[DataSource] = []
    # 한약재(herbal: true, KADA 한약재 가이드라인)는 약가마스터의 같은 이름 제품보다 먼저 — 예: "마황"
    kr = None if (hit and hit[0] == "substance") or (hand_product and (hand_product["kind"] == "category" or hand_product.get("herbal"))) \
        else _kr_lookup(query)
    if hit and hit[0] == "substance":
        kind = "substance"
        pairs = [_ingredient(hit[1])]
        reviewed = pairs[0][1]
    elif kr:
        kind, note, candidates = kr["kind"], kr["note"], kr.get("candidates", [])
        pairs = [(i, False) for i in kr["ingredients"]]
        sources = [_kr_data_source()]
    elif hand_product:
        kind, supplement = hand_product["kind"], hand_product.get("supplement", False)
        reviewed, note, extra = hand_product["reviewed"], hand_product.get("note"), hand_product.get("links", [])
        pairs = [_ingredient(i) for i in hand_product["ingredients"]]
        reviewed = reviewed and all(r for _, r in pairs)
    elif wada_items := _wada()[1].get(normalize(query)):
        kind = "substance"
        pairs = [(_wada_ingredient(wada_items), False)]
    elif kr_name := _kr_by_ingredient_name(query):
        kind, note = kr_name["kind"], kr_name["note"]
        pairs = [(i, False) for i in kr_name["ingredients"]]
        sources = [_kr_data_source()]
    else:
        pairs = [_ingredient(i) for i in _partial(query)]  # 판정 없이 주의 성분만

    ingredients = [ing for ing, _ in pairs]
    if kr:
        status: CheckStatus = kr["status"]
    elif kind in ("substance", "product"):
        status = min((i.status for i in ingredients), key=STRICTNESS.index) if ingredients else "UNKNOWN"
    else:
        status = "UNKNOWN"

    return CheckResult(
        query=query,
        matched_kind=kind,
        status=status,
        ingredients=ingredients,
        timing=timing,
        country=country,
        route=route,
        steps=_steps(status, kind, route, timing, supplement, note),
        links=_links(route, status, extra),
        supplement_warning=supplement,
        list_version=substances["list_version"],
        reviewed=reviewed,
        candidates=candidates,
        data_sources=sources,
    )


def unreviewed() -> list[str]:
    """§10 G2: 연구진 검토 전 항목. DEMO_MODE=0에서 하나라도 있으면 서버가 시작을 거부한다."""
    substances, products, _, _ = _tables()
    out = [f"substances.json:{k}" for k, v in substances["substances"].items() if not v["reviewed"]]
    out += [f"products.json:{k}" for k, v in products["products"].items() if not v["reviewed"]]
    # 자동 추출본은 파일 단위로 검토한다(추출 방법 + 섹션별 표본 + 예외 테스트) — 사용자·연구진 승인 대기
    if not _kr()[0]["meta"]["reviewed"]:
        out.append("kr_products.json.gz")
    if not _wada()[0]["reviewed"]:
        out.append(f"wada/processed/prohibited_list_{substances['list_version']}.json")
    return out


def list_expires() -> date:
    """§10 G3: 조회표와 WADA 추출본 중 먼저 끝나는 유효일. 매년 1월 1일 새 목록이 발효된다."""
    return min(date.fromisoformat(_tables()[0]["list_expires"]), date.fromisoformat(_wada()[0]["list_expires"]))
