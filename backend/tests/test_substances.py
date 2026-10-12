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
    # + dro_countries.json + WADA 추출본(파일 단위 검토)
    assert len(pending) == len(TABLES["substances.json"]["substances"]) + len(TABLES["products.json"]["products"]) + 2
    assert "wada/prohibited_list_2026.json" in pending


def test_list_expires_matches_list_version():
    expires = substances.list_expires()
    assert (expires.year, expires.month, expires.day) == (int(TABLES["substances.json"]["list_version"]), 12, 31)


# ---------- WADA 금지목록 자동 추출본 (손 조회표에 없는 이름) ----------

@pytest.mark.parametrize("query,status,wada_class", [
    ("Bumetanide", "PROHIBITED", "S5"),            # 상시 금지
    ("cocaine", "IN_COMPETITION_ONLY", "S6.A"),    # 경기기간 중 금지
    ("Budesonide", "IN_COMPETITION_ONLY", "S9"),   # 투여 경로 조건 안내 포함
    ("Vilanterol", "UNKNOWN", "S3"),               # 흡입 용량 예외 → 조건 충족 여부를 모름
    ("Dorzolamide", "UNKNOWN", "S5"),              # 점안 예외
    ("nicotine", "NOT_LISTED_VERIFY", "S6"),       # 조건 없이 "금지 아님"(모니터링)
    ("bisoprolol", "NOT_LISTED_VERIFY", "P1"),     # 역도는 P1 종목이 아님
])
def test_wada_extract_status_rules(query, status, wada_class):
    r = check(query, "KR", "in_competition")
    assert (r.matched_kind, r.status, r.ingredients[0].wada_class) == ("substance", status, wada_class)
    assert r.ingredients[0].source_url.startswith("https://www.wada-ama.org/")
    assert r.reviewed is False


def test_wada_exception_never_shows_as_cleared():
    """예외 성분은 '허용'처럼 보이면 안 된다: 조건 안내가 반드시 붙는다."""
    r = check("Vilanterol", "KR", "in_competition")
    assert substances.EXCEPTION_NOTE in r.ingredients[0].note
    assert "원문:" in r.ingredients[0].note


def test_wada_route_condition_for_glucocorticoids():
    assert "흡입" in check("Budesonide", "KR", "in_competition").ingredients[0].note


def test_wada_footnote_condition_is_shown_but_listing_lines_are_not():
    assert "local administration" in check("adrenaline", "KR", "in_competition").ingredients[0].note
    assert check("Bumetanide", "KR", "in_competition").ingredients[0].note is None


@pytest.mark.parametrize("query", ["pseudoephedrine", "caffeine", "CBD", "salbutamol"])
def test_hand_table_takes_priority_over_extract(query):
    """손 조회표(기준치 수치·한국어 설명·항목별 검토)가 있으면 그것을 쓴다."""
    r = check(query, "KR", "in_competition")
    assert r.ingredients[0].name_ko != r.ingredients[0].name_en  # 손 조회표 항목은 한국어 이름이 있다


def test_list_expiry_covers_both_tables():
    assert substances.list_expires().isoformat() == "2026-12-31"
