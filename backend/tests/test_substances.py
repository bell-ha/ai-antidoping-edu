"""약물 확인 판정 표 테스트 (D10, D11, D12). 사실관계 자체가 아니라 판정 규칙을 고정한다."""

import json

import pytest

from app.drugs import substances
from app.config import DRUGS
from app.drugs.substances import check

TABLES = {name: json.loads((DRUGS / "curated" / name).read_text(encoding="utf-8"))
          for name in ("substances.json", "products.json")}
HERBS = json.loads((DRUGS / "kada" / "processed" / "herbal_medicine_2025.json").read_text(encoding="utf-8"))["herbs"]


def test_no_allowed_status_exists():
    """'허용' 상태는 없다. 목록에 없는 성분도 '확인 필요'다."""
    statuses = {s["status"] for s in TABLES["substances.json"]["substances"].values()}
    assert statuses <= {"PROHIBITED", "IN_COMPETITION_ONLY", "THRESHOLD", "NOT_LISTED_VERIFY"}


def test_every_entry_has_source_and_review_flag():
    for s in TABLES["substances.json"]["substances"].values():
        assert s["source_url"].startswith("https://www.wada-ama.org/")
        assert isinstance(s["reviewed"], bool)
    for p in [*TABLES["products.json"]["products"].values(), *HERBS.values()]:
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
    assert not any("TUE" in link.label for link in r.links)  # 확인처·TUE 안내 링크 없음(2026-10-17 사용자)


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


@pytest.mark.parametrize("query", ["슈도에페드린 시럽", "에페드린 다이어트약"])
def test_partial_name_is_never_judged(query):
    """이름이 일부만 맞으면 다른 성분이 더 있을 수 있으므로 판정하지 않는다."""
    r = check(query, "KR", "in_competition")
    assert (r.matched_kind, r.status) == ("unmatched", "UNKNOWN")
    assert all(i.status != "NOT_LISTED_VERIFY" for i in r.ingredients)  # 주의 성분에는 문제 성분만


def test_unmatched_is_unknown():
    r = check("처음보는약", "KR", "unknown")
    assert (r.matched_kind, r.status, r.ingredients) == ("unmatched", "UNKNOWN", [])


@pytest.mark.parametrize("country,route", [("KR", "kada"), ("kr", "kada"), ("US", "local_unverified"), ("TH", "local_unverified")])
def test_country_routes_and_no_confirm_elsewhere_links(country, route):
    """다른 기관에서 다시 확인하라는 링크는 붙이지 않는다(2026-10-17 사용자). 해외 제품이면 성분이 다를 수 있다는 사실만."""
    r = check("감기약", country, "unknown")
    assert r.route == route
    assert r.links == []  # 확인처 링크 없음(제품군·한약재 자료 출처 링크만 붙는다)



def test_supplements_always_warn_even_if_ingredient_not_listed():
    r = check("크레아틴 보충제", "KR", "unknown")
    assert r.status == "NOT_LISTED_VERIFY"
    assert r.supplement_warning
    assert any("성분표에 없는" in s for s in r.steps)


def test_herbal_medicine_in_general_is_not_judged():
    """한약 일반은 처방마다 달라 판정하지 않는다(UNKNOWN). 가이드라인의 한약재 11종은 따로 판정(아래)."""
    r = check("한약", "KR", "in_competition")
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
    for pid, p in [*TABLES["products.json"]["products"].items(), *HERBS.items()]:
        for name in [pid, *p["aliases"]]:
            key = substances.normalize(name)
            assert seen.setdefault(key, pid) == pid, name


def test_unreviewed_lists_every_pending_entry():
    """§10 G2: 지금은 전 항목이 검토 전이다. 연구진이 reviewed:true로 바꾸면 이 목록에서 빠진다."""
    pending = substances.unreviewed()
    # + KADA 한약재 11종 + 한글 제품명 조회표 + WADA 추출본 + KADA 분류 이름(파일 단위 검토)
    assert len(pending) == (len(TABLES["substances.json"]["substances"]) + len(TABLES["products.json"]["products"])
                            + len(HERBS) + 3)
    assert "herbal_medicine_2025.json:마황" in pending
    assert "kr_products.json.gz" in pending
    assert "wada/processed/prohibited_list_2026.json" in pending


def test_list_expires_matches_list_version():
    expires = substances.list_expires()
    assert (expires.year, expires.month, expires.day) == (int(TABLES["substances.json"]["list_version"]), 12, 31)


# ---------- WADA 금지목록 자동 추출본 (손 조회표에 없는 이름) ----------

@pytest.mark.parametrize("query,status,wada_class", [
    ("Bumetanide", "PROHIBITED", "S5"),            # 상시 금지
    ("cocaine", "IN_COMPETITION_ONLY", "S6.A"),    # 경기기간 중 금지
    ("Budesonide", "IN_COMPETITION_ONLY", "S9"),   # 투여 경로 조건 안내 포함
    ("Vilanterol", "CONDITIONAL", "S3"),           # 흡입 용량 예외 → 조건 충족 여부를 모름
    ("Dorzolamide", "CONDITIONAL", "S5"),          # 점안 예외
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


def test_conditional_status_gets_own_step():
    r = check("Vilanterol", "KR", "in_competition")
    assert r.status == "CONDITIONAL"
    assert not any("TUE" in link.label for link in r.links)
    assert any("조건(용량" in s for s in r.steps)


@pytest.mark.parametrize("query", ["enobosarm", "ostarine", "Enobosarm (ostarine)", "에노보삼", "오스타린"])
def test_parenthetical_names_match_on_their_own(query):
    assert check(query, "KR", "unknown").ingredients[0].name_en == "enobosarm (ostarine)"


@pytest.mark.parametrize("a,b", [("ɑ-PVP", "a-pvp"), ("3ß-hydroxy", "3β-hydroxy"), ("[Lys8]-vasopressin", "lys8 vasopressin")])
def test_normalize_unifies_greek_lookalikes_and_brackets(a, b):
    assert substances.normalize(a) == substances.normalize(b)


def test_short_fragments_are_not_indexed_but_whole_names_are():
    variants = substances.name_variants("metamfetamine (d-)")
    assert "metamfetamine" in variants and "d" not in variants
    assert check("대마", "KR", "unknown").matched_kind == "substance"  # 두 글자 한글 별칭


# ---------- 한글 제품명 (심평원 약가마스터, 공공누리 제1유형) ----------

@pytest.mark.parametrize("query,kind,status,flagged", [
    ("타이레놀콜드-에스정", "product", "THRESHOLD", "pseudoephedrine"),      # 복합 감기약 속 기준치 성분
    ("타이레놀 콜드", "product", "THRESHOLD", "pseudoephedrine"),            # 띄어쓰기·앞부분 일치
    ("콘서타", "product", "IN_COMPETITION_ONLY", "methylphenidate"),
    ("소론도정", "product", "IN_COMPETITION_ONLY", "prednisolone"),        # S9 + 경구 → 경기기간 중 금지
    ("더모베이트", "product", "CONDITIONAL", "clobetasol"),                # 목록에 이름 없음 → ATC D07 계열 + 외용
    ("라식스", "product", "PROHIBITED", "furosemide"),                     # 정제·주사 제형만 달라 판정이 같음
])
def test_korean_product_names(query, kind, status, flagged):
    r = check(query, "KR", "in_competition")
    assert (r.matched_kind, r.status) == (kind, status)
    assert any(flagged in i.name_en.lower() and i.status == status for i in r.ingredients)
    assert r.data_sources and "공공누리" in r.data_sources[0].label


def test_ambiguous_product_prefix_is_not_judged():
    """'타이레놀'로 시작하는 제품은 성분이 서로 달라 판정하지 않고, 후보와 문제 성분만 보여준다."""
    r = check("타이레놀", "KR", "in_competition")
    assert (r.matched_kind, r.status) == ("category", "UNKNOWN")
    assert 2 <= len(r.candidates) <= substances.MAX_CANDIDATES
    assert any("pseudoephedrine" in i.name_en for i in r.ingredients)


def test_product_without_ingredient_data_is_unknown_not_cleared():
    """두 원본의 갱신 시점 차이로 성분이 없는 제품은 UNKNOWN이어야 한다(NOT_LISTED_VERIFY로 가면 안 됨)."""
    data, _, _ = substances._kr()
    row = next(p for p in data["products"] if p[3] not in data["groups"])
    assert substances._kr_ingredients(row[3], row[4]) is None
    r = check(row[0], "KR", "unknown")
    assert r.status == "UNKNOWN"


@pytest.mark.parametrize("raw,expected", [
    ("pseudoephedrine hydrochloride", "pseudoephedrine"),
    ("salbutamol sulfate (as salbutamol)", "salbutamol"),
    ("dl-methylephedrine hydrochloride", "methylephedrine"),
    ("dexamethasone sodium phosphate", "dexamethasone"),
])
def test_clean_english_strips_salts_and_prefixes(raw, expected):
    assert substances.clean_english(raw) == expected


@pytest.mark.parametrize("raw,status", [
    ("dl-methylephedrine hydrochloride", "THRESHOLD"),   # ephedrine이 아니라 가장 긴 methylephedrine
    ("triamcinolone acetonide", "IN_COMPETITION_ONLY"),  # WADA에 염 이름째로 있음
    ("beclomethasone dipropionate", "IN_COMPETITION_ONLY"),  # INN 표기 beclometasone
])
def test_product_ingredient_resolution(raw, status):
    assert substances.resolve_english(raw).status == status


def test_route_changes_glucocorticoid_and_inhaled_beta2_status():
    pred = substances.resolve_english("prednisolone")
    assert substances.by_route(pred, "내복", "정제").status == "IN_COMPETITION_ONLY"
    assert substances.by_route(pred, "외용", "연고제").status == "CONDITIONAL"
    assert substances.by_route(pred, "외용", "좌제").status == "IN_COMPETITION_ONLY"  # 직장 투여
    salb = substances.resolve_english("salbutamol sulfate")
    assert substances.by_route(salb, "내복", "정제").status == "PROHIBITED"   # 흡입 예외 아님
    assert substances.by_route(salb, "외용", "분무제 및 흡입제").status == "THRESHOLD"


def test_no_unmatched_product_ingredient_with_banned_stems():
    """커버리지 보고: 제품 성분 중 어느 목록과도 맞지 않는데 금지 계열 어간을 가진 이름이 있으면 실패.
    알려진 예외(비금지 물질이거나 외용 복합제라 계열 판정이 안 되는 것)는 사유와 함께 적어 둔다."""
    stems = ["ephedrine", "phenidate", "semide", "thiazide", "terol", "morphine", "nandrol", "testoster",
             "stanozol", "clenbut", "fetamine", "phetamine", "modafinil", "sibutramine", "tramadol",
             "cortisone", "metasone", "methasone", "sonide", "olone"]
    known = {
        "enoxolone": "감초 추출 성분(글리시레트산), 스테로이드 아님",
        "sitosterol": "식물성 스테롤, 금지 아님",
        "β-sitosterol": "식물성 스테롤, 금지 아님",
        "serenoa repens lipidosterolic ext.": "쏘팔메토 추출물, 금지 아님",
        "hydrocodone bitartrate": "WADA 모니터링 대상(금지 아님)",
    }
    data = substances._kr()[0]
    found = set()
    for row in data["products"]:
        for ing in substances._kr_ingredients(row[3], row[4]) or ():
            name = ing.name_en.lower()
            if ing.note == substances.NO_MATCH_NOTE and any(s in name for s in stems):
                found.add(name)
    assert found <= {k.lower() for k in known}, sorted(found - {k.lower() for k in known})


def test_unlisted_glucocorticoids_follow_s9_route_rules():
    """목록에 예시로 없는 당질코르티코이드는 손 조회표에서 S9로 — 외용 복합제 속이면 조건부, 경구면 경기기간 중 금지."""
    for raw in ("diflucortolone valerate", "fluocinolone acetonide", "clobetasol propionate"):
        ing = substances.resolve_english(raw)
        assert ing.wada_class == "S9"
        assert substances.by_route(ing, "외용", "크림제").status == "CONDITIONAL"
        assert substances.by_route(ing, "내복", "정제").status == "IN_COMPETITION_ONLY"


def test_stimulant_class_code_is_not_a_verdict():
    """N06BA에는 금지가 아닌 약(atomoxetine)도 있어 계열만으로 금지라고 하지 않는다."""
    unmatched = substances.Ingredient(name_ko="x", name_en="x", status="NOT_LISTED_VERIFY",
                                      note=substances.NO_MATCH_NOTE, source_url=substances.HIRA_URL)
    assert substances.by_atc(unmatched, "N06BA09").status == "UNKNOWN"
    assert substances.by_atc(unmatched, "C03CA01").status == "PROHIBITED"


# ---------- 한글 성분명 (약가마스터 제품명 안의 성분명) ----------

@pytest.mark.parametrize("query,en,status", [
    ("펜터민", "phentermine", "IN_COMPETITION_ONLY"),
    ("메틸프레드니솔론", "methylprednisolone", "IN_COMPETITION_ONLY"),  # 예전엔 부분 일치로 prednisolone이 나왔음
    ("스피로노락톤", "spironolactone", "PROHIBITED"),
    ("툴로부테롤", "tulobuterol", "PROHIBITED"),
    ("소마트로핀", "somatropin", "PROHIBITED"),
])
def test_korean_ingredient_name_found_inside_product_names(query, en, status):
    r = check(query, "KR", "in_competition")
    assert (r.matched_kind, r.status) == ("substance", status)
    assert [i.name_en for i in r.ingredients] == [en]
    assert r.data_sources and "공공누리" in r.data_sources[0].label


@pytest.mark.parametrize("query", ["펜타닐", "에피네프린", "인슐린"])
def test_korean_ingredient_name_shared_by_several_ingredients_is_not_judged(query):
    """'펜타닐'은 레미펜타닐·수펜타닐 제품명에도 들어 있다. 성분을 하나로 특정할 수 없으면 판정하지 않는다."""
    assert check(query, "KR", "in_competition").status == "UNKNOWN"


@pytest.mark.parametrize("herb, status, ingredient", [("마황", "THRESHOLD", "ephedrine"), ("부자", "PROHIBITED", "higenamine"),
                                                      ("마전자", "IN_COMPETITION_ONLY", "strychnine")])
def test_kada_herbs_are_judged_by_detected_ingredients(herb, status, ingredient):
    """KADA 한약재 가이드라인(KIST 2024 분석)의 11종: 검출 성분으로 판정."""
    r = check(herb, "KR", "unknown")
    assert r.status == status and ingredient in [i.name_en for i in r.ingredients]


def test_korean_class_names_come_from_kada_list():
    """판정 카드의 한글 분류명(KADA 2026 금지목록 국문판, scripts/build_kada.py)."""
    r = check("에페드린", "KR", "unknown")
    assert (r.ingredients[0].wada_class, r.ingredients[0].wada_class_ko) == ("S6.B", "특정 흥분제")
    assert substances.class_ko("S2.1.3") == "GATA 억제제"
    assert substances.class_ko("S2.1.9") == substances.class_ko("S2.1")  # 세부 이름이 없으면 상위 분류


def test_supplement_products_carry_contamination_warning():
    for q in ("프로틴", "단백질", "보충제", "크레아틴", "히게나민"):  # 제품군 이름이든, 보충제에 들어 있는 성분 이름이든
        assert check(q, "KR", "unknown").supplement_warning, q
    assert not check("슈도에페드린", "KR", "unknown").supplement_warning
