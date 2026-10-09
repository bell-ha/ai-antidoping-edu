"""약물 확인 판정 표 테스트 (D10, D11, D12). 사실관계 자체가 아니라 판정 규칙을 고정한다."""

import json

import pytest

from app import substances
from app.config import DATA
from app.substances import check

TABLES = {name: json.loads((DATA / name).read_text(encoding="utf-8"))
          for name in ("substances.json", "products.json", "dro_countries.json")}


def test_no_allowed_status_exists():
    """'허용' 상태는 없다. 목록에 없는 성분도 '확인 필요'다."""
    statuses = {s["status"] for s in TABLES["substances.json"]["substances"].values()}
    assert statuses <= {"PROHIBITED", "IN_COMPETITION_ONLY", "THRESHOLD", "NOT_LISTED_VERIFY"}


def test_every_entry_has_source_and_review_flag():
    for s in TABLES["substances.json"]["substances"].values():
        assert s["source_url"].startswith("https://www.wada-ama.org/")
        assert isinstance(s["reviewed"], bool)
    for p in TABLES["products.json"]["products"].values():
        assert isinstance(p["reviewed"], bool)
        assert all(i in TABLES["substances.json"]["substances"] for i in p["ingredients"])


def test_category_is_always_unknown_with_caution_list():
    """S2: '감기약'은 제품군이라 판정하지 않고 주의 성분을 보여준다."""
    r = check("감기약", "KR", "in_competition")
    assert (r.matched_kind, r.status) == ("category", "UNKNOWN")
    assert "슈도에페드린" in [i.name_ko for i in r.ingredients]
    assert r.route == "kada"


def test_s2_requery_by_ingredient_gives_threshold():
    r = check("슈도에페드린", "KR", "in_competition")
    assert (r.matched_kind, r.status, r.ingredients[0].wada_class) == ("substance", "THRESHOLD", "S6.B")
    assert any("TUE" in link.label for link in r.links)


def test_timing_never_lowers_status():
    """경기기간 외라고 해도 경기기간 중 금지 성분의 상태는 그대로, 잔류 안내가 붙는다."""
    r = check("메틸페니데이트", "KR", "out_of_competition")
    assert r.status == "IN_COMPETITION_ONLY"
    assert any("몸에 남아" in s for s in r.steps)


def test_unknown_timing_is_judged_as_in_competition():
    r = check("슈도에페드린", "KR", "unknown")
    assert r.status == "THRESHOLD"
    assert any("경기기간 중 기준" in s for s in r.steps)


def test_product_takes_strictest_ingredient():
    r = check("벤토린", "KR", "in_competition")
    assert (r.matched_kind, r.status) == ("product", "THRESHOLD")


@pytest.mark.parametrize("query", ["타이레놀 콜드", "슈도에페드린 시럽", "에페드린 다이어트약"])
def test_partial_name_is_never_judged(query):
    """이름이 일부만 맞으면 다른 성분이 더 있을 수 있으므로 판정하지 않는다."""
    r = check(query, "KR", "in_competition")
    assert (r.matched_kind, r.status) == ("unmatched", "UNKNOWN")
    assert all(i.status != "NOT_LISTED_VERIFY" for i in r.ingredients)  # 주의 성분에는 문제 성분만


def test_unmatched_is_unknown_and_points_to_kada():
    r = check("처음보는약", "KR", "unknown")
    assert (r.matched_kind, r.status, r.ingredients) == ("unmatched", "UNKNOWN", [])
    assert r.links[0].url.startswith("https://www.kada-ad.or.kr/")


@pytest.mark.parametrize("country,route", [("KR", "kada"), ("kr", "kada"), ("US", "globaldro"), ("JP", "globaldro"),
                                           ("TH", "local_unverified")])
def test_country_routes(country, route):
    r = check("감기약", country, "unknown")
    assert r.route == route
    assert any(link.label.startswith("KADA") for link in r.links)  # 해외에서도 KADA는 항상
    assert ("Global DRO" in [link.label for link in r.links]) == (route == "globaldro")


def test_korea_is_not_a_global_dro_country():
    """Global DRO는 한국 제품을 다루지 않고 KADA 검색으로 안내한다(globaldro.com, 2026-10-08 확인)."""
    assert "KR" not in TABLES["dro_countries.json"]["countries"]


def test_supplements_always_warn_even_if_ingredient_not_listed():
    r = check("크레아틴 보충제", "KR", "unknown")
    assert r.status == "NOT_LISTED_VERIFY"
    assert r.supplement_warning
    assert any("성분표에 없는" in s for s in r.steps)


def test_herbal_medicine_is_not_judged():
    """KADA는 한약 성분을 판정하지 않는다 → 한약·마황은 UNKNOWN + KADA 한약 안내."""
    for q in ("한약", "마황"):
        r = check(q, "KR", "in_competition")
        assert r.status == "UNKNOWN"
        assert any("한약" in link.label for link in r.links)


def test_weightlifting_is_not_a_beta_blocker_sport():
    r = check("프로프라놀롤", "KR", "in_competition")
    assert r.status == "NOT_LISTED_VERIFY"
    assert "역도" in (r.ingredients[0].note or "")


def test_reviewed_is_false_until_research_team_reviews():
    assert check("슈도에페드린", "KR", "unknown").reviewed is False
    assert check("처음보는약", "KR", "unknown").reviewed is False


def test_names_are_unique_across_tables():
    """같은 이름이 성분과 제품 양쪽에 있으면 어느 쪽으로 판정되는지 모호해진다."""
    seen: dict[str, str] = {}
    for sid, s in TABLES["substances.json"]["substances"].items():
        for name in [s["name_ko"], s["name_en"], *s["aliases"]]:
            key = substances.normalize(name)
            assert seen.setdefault(key, sid) == sid, name
    for pid, p in TABLES["products.json"]["products"].items():
        for name in [pid, *p["aliases"]]:
            key = substances.normalize(name)
            assert seen.setdefault(key, pid) == pid, name


def test_unreviewed_lists_every_pending_entry():
    """§10 G2: 지금은 전 항목이 검토 전이다. 연구진이 reviewed:true로 바꾸면 이 목록에서 빠진다."""
    pending = substances.unreviewed()
    assert len(pending) == len(TABLES["substances.json"]["substances"]) + len(TABLES["products.json"]["products"]) + 1


def test_list_expires_matches_list_version():
    expires = substances.list_expires()
    assert (expires.year, expires.month, expires.day) == (int(TABLES["substances.json"]["list_version"]), 12, 31)
