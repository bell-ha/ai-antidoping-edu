"""약물·보충제 확인 (D10, D11, D12). 판정은 조회표가 하고 LLM은 설명만 한다.

조회표: data/substances.json(성분, 손으로 정리·검토), data/products.json(제품·제품군), data/dro_countries.json,
data/wada/prohibited_list_<연도>.json(WADA 금지목록 PDF 자동 추출, analysis/wada_extract.py).
손 조회표가 우선이고, 거기 없는 이름만 WADA 추출본에서 찾는다(정확히 일치하는 영문 이름·동의어만).
- "허용" 상태는 없다. 목록에 없는 성분도 NOT_LISTED_VERIFY(확인 필요)다.
- 제품군(category)은 성분을 특정할 수 없으므로 항상 UNKNOWN이고, 성분 목록은 '주의 성분'이다.
- WADA 추출 항목의 예외(용량·경로·용도 조건)는 조건 충족 여부를 알 수 없으므로 UNKNOWN + 조건 안내.
  조건 없이 "금지 아님"인 항목(모니터링 대상 등)만 NOT_LISTED_VERIFY.
- 사용 시기는 상태를 낮추지 않는다. 경기기간 중에만 금지인 성분을 경기기간 외에 쓴다고 해도
  상태는 그대로 두고, 절차에서 경기 전 잔류 가능성을 안내한다(D11 "모름 = 경기기간 중"의 연장).
"""

import json
import re
from datetime import date
from functools import cache

from app.config import DATA
from app.schemas import CheckResult, CheckStatus, CountryRoute, Ingredient, OfficialLink, Timing

STRICTNESS: list[CheckStatus] = ["PROHIBITED", "IN_COMPETITION_ONLY", "THRESHOLD", "NOT_LISTED_VERIFY", "UNKNOWN"]


def _load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def normalize(text: str) -> str:
    return re.sub(r"[\s\-_·()（）]", "", text).lower()


EXCEPTION_NOTE = "조건(용량·투여 경로·용도)에 따라 금지되지 않을 수 있어요. 해당하는지는 KADA나 팀 닥터에게 확인하세요."
P1_NOTE = "베타차단제는 지정 종목에서만 금지되며 역도는 해당하지 않아요(다른 종목은 확인 필요)."


@cache
def _wada() -> tuple[dict, dict[str, list[dict]]]:
    """WADA 추출본과 이름 색인(정규화한 이름·동의어 → 항목들). 같은 이름이 금지와 예외로 함께 나올 수 있다."""
    version = _tables()[0]["list_version"]
    wada = _load(f"wada/prohibited_list_{version}.json")
    if "weightlifting" in {x.lower() for x in wada["sections"]["P1"].get("sports", [])}:
        raise RuntimeError("P1 종목에 역도가 있음 — P1 규칙(NOT_LISTED_VERIFY)을 다시 정해야 함")
    index: dict[str, list[dict]] = {}
    for item in wada["items"]:
        for name in [item["name"], *item.get("synonyms", [])]:
            index.setdefault(normalize(name), []).append(item)
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
            status, note = "UNKNOWN", EXCEPTION_NOTE
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
    substances = _load("substances.json")
    products = _load("products.json")
    dro = _load("dro_countries.json")
    index: dict[str, tuple[str, str]] = {}
    for sid, s in substances["substances"].items():
        for name in [s["name_ko"], s["name_en"], *s.get("aliases", [])]:
            index[normalize(name)] = ("substance", sid)
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


def _route(country: str) -> CountryRoute:
    if country == "KR":
        return "kada"
    return "globaldro" if country in _tables()[2]["countries"] else "local_unverified"


def _links(route: CountryRoute, status: CheckStatus, extra: list[dict]) -> list[OfficialLink]:
    _, _, dro, _ = _tables()
    links = [OfficialLink(**dro["kada_search"])]
    if route == "globaldro":
        links.append(OfficialLink(label="Global DRO", url=dro["source_url"]))
    if status in ("PROHIBITED", "IN_COMPETITION_ONLY", "THRESHOLD"):
        links.append(OfficialLink(**dro["kada_tue"]))
    links += [OfficialLink(**e) for e in extra]
    return links


def _steps(status: CheckStatus, kind: str, route: CountryRoute, timing: Timing, supplement: bool,
           note: str | None) -> list[str]:
    steps: list[str] = []
    if kind in ("category", "unmatched"):
        steps.append("제품 포장이나 설명서에서 성분명을 확인하고, 성분명으로 다시 검색하세요.")
    if note:
        steps.append(note)
    if status == "PROHIBITED":
        steps.append("경기기간과 관계없이 항상 금지된 성분이에요. 복용하지 말고 팀 닥터와 상의하세요.")
    elif status == "IN_COMPETITION_ONLY":
        steps.append("경기기간 중 금지된 성분이에요.")
    elif status == "THRESHOLD":
        steps.append("정해진 용량이나 소변 농도 기준을 넘으면 위반이에요. 복용량과 시점에 따라 달라지므로 혼자 판단하지 마세요.")
    elif status == "NOT_LISTED_VERIFY":
        steps.append("금지목록에서 확인되지 않았어요. 그래도 복용 전 공식 검색으로 최종 확인하세요.")
    if status in ("IN_COMPETITION_ONLY", "THRESHOLD") and timing == "out_of_competition":
        steps.append("경기기간 전에 복용해도 경기 때까지 몸에 남아 검출될 수 있어요. 대회 일정을 팀 닥터와 함께 확인하세요.")
    if timing == "unknown":
        steps.append("사용 시기를 모르면 경기기간 중 기준으로 판단했어요.")
    if status in ("PROHIBITED", "IN_COMPETITION_ONLY", "THRESHOLD"):
        steps.append("치료 목적으로 꼭 필요하다면 치료목적사용면책(TUE) 대상인지 KADA에 문의하세요.")
    if supplement:
        steps.append("보충제는 성분표에 없는 금지물질이 섞여 있을 수 있어요. 성분이 문제없어 보여도 위험이 남아요.")
    if route == "kada":
        steps.append("KADA 금지약물 검색에서 제품명이나 성분명으로 최종 확인하세요.")
    elif route == "globaldro":
        steps.append("해외에서 산 제품은 Global DRO에서 구매 국가를 골라 확인하고, KADA에도 문의하세요.")
    else:
        steps.append("이 국가의 제품은 국내 제품과 성분이 같다고 보장할 수 없어요. 성분표를 KADA에 문의하세요.")
    return steps


def check(query: str, country: str, timing: Timing) -> CheckResult:
    substances, products, _, _ = _tables()
    country = country.upper()
    route = _route(country)
    hit = _match(query)

    kind, ids, supplement, reviewed, note, extra = "unmatched", [], False, False, None, []
    wada_items = None if hit else _wada()[1].get(normalize(query))
    if wada_items:
        kind = "substance"
    elif hit and hit[0] == "substance":
        kind, ids = "substance", [hit[1]]
    elif hit:
        p = products["products"][hit[1]]
        kind, ids, supplement = p["kind"], p["ingredients"], p.get("supplement", False)
        reviewed, note, extra = p["reviewed"], p.get("note"), p.get("links", [])
    else:
        ids = _partial(query)  # 판정 없이 주의 성분만: matched_kind는 unmatched, 상태는 UNKNOWN

    pairs = [_ingredient(i) for i in ids] if not wada_items else [(_wada_ingredient(wada_items), False)]
    ingredients = [ing for ing, _ in pairs]
    if kind in ("substance", "product"):
        status: CheckStatus = min((i.status for i in ingredients), key=STRICTNESS.index) if ingredients else "UNKNOWN"
        reviewed = all(r for _, r in pairs) and (kind == "substance" or reviewed)
    else:
        status = "UNKNOWN"
        reviewed = reviewed and all(r for _, r in pairs)

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
    )


def unreviewed() -> list[str]:
    """§10 G2: 연구진 검토 전 항목. DEMO_MODE=0에서 하나라도 있으면 서버가 시작을 거부한다."""
    substances, products, dro, _ = _tables()
    out = [f"substances.json:{k}" for k, v in substances["substances"].items() if not v["reviewed"]]
    out += [f"products.json:{k}" for k, v in products["products"].items() if not v["reviewed"]]
    if not dro["reviewed"]:
        out.append("dro_countries.json")
    # 자동 추출본은 파일 단위로 검토한다(추출 방법 + 섹션별 표본 + 예외 테스트) — 사용자·연구진 승인 대기
    if not _wada()[0]["reviewed"]:
        out.append(f"wada/prohibited_list_{substances['list_version']}.json")
    return out


def list_expires() -> date:
    """§10 G3: 조회표와 WADA 추출본 중 먼저 끝나는 유효일. 매년 1월 1일 새 목록이 발효된다."""
    return min(date.fromisoformat(_tables()[0]["list_expires"]), date.fromisoformat(_wada()[0]["list_expires"]))
