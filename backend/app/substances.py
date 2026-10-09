"""약물·보충제 확인 (D10, D11, D12). 판정은 조회표가 하고 LLM은 설명만 한다.

조회표: data/substances.json(성분), data/products.json(제품·제품군), data/dro_countries.json.
- "허용" 상태는 없다. 목록에 없는 성분도 NOT_LISTED_VERIFY(확인 필요)다.
- 제품군(category)은 성분을 특정할 수 없으므로 항상 UNKNOWN이고, 성분 목록은 '주의 성분'이다.
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
    if hit and hit[0] == "substance":
        kind, ids = "substance", [hit[1]]
    elif hit:
        p = products["products"][hit[1]]
        kind, ids, supplement = p["kind"], p["ingredients"], p.get("supplement", False)
        reviewed, note, extra = p["reviewed"], p.get("note"), p.get("links", [])
    else:
        ids = _partial(query)  # 판정 없이 주의 성분만: matched_kind는 unmatched, 상태는 UNKNOWN

    pairs = [_ingredient(i) for i in ids]
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
    return out


def list_expires() -> date:
    """§10 G3: 조회표가 따르는 금지목록의 마지막 유효일. 매년 1월 1일 새 목록이 발효된다."""
    return date.fromisoformat(_tables()[0]["list_expires"])
