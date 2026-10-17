"""WADA 금지목록 자동 추출본(knowledge/drugs/wada/processed/prohibited_list_2026.json) 고정 테스트.

원문(2026 금지목록 PDF)에서 직접 확인한 분류를 고정한다. 특히 "금지 아님"인 예외가 금지로 바뀌지 않는지.
추출 스크립트: scripts/wada_extract.py + 손 보정 knowledge/drugs/wada/processed/wada_manual_2026.yaml
"""

import json
import re
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[2] / "knowledge/drugs/wada/processed/prohibited_list_2026.json"
LIST = json.loads(DATA.read_text(encoding="utf-8"))


def kinds(name: str) -> set[tuple[str, str]]:
    n = name.lower()
    return {(i["section"], i["kind"]) for i in LIST["items"] if i["name"].lower() == n or n in (s.lower() for s in i["synonyms"])}


def test_metadata():
    assert LIST["list_version"] == "2026" and LIST["list_expires"] == "2026-12-31"
    assert LIST["reviewed"] is False and len(LIST["source_sha256"]) == 64
    assert "닫힌 목록이 아님" in LIST["caution"]


@pytest.mark.parametrize("name", ["cathine", "ephedrine", "methylephedrine", "pseudoephedrine"])
def test_s6_threshold_substances(name):
    assert kinds(name) == {("S6", "threshold")}


@pytest.mark.parametrize("name", ["bupropion", "caffeine", "nicotine", "phenylephrine", "phenylpropanolamine", "pipradrol", "synephrine"])
def test_s6_monitoring_program_is_not_prohibited(name):
    assert kinds(name) == {("S6", "exception")}


@pytest.mark.parametrize("name,section", [("clonidine", "S6"), ("naphazoline", "S6"), ("cannabidiol", "S8"),
                                          ("drospirenone", "S5"), ("dorzolamide", "S5"), ("felypressin", "S5")])
def test_named_exceptions(name, section):
    assert kinds(name) == {(section, "exception")}


@pytest.mark.parametrize("name", ["salbutamol", "formoterol", "salmeterol", "vilanterol"])
def test_inhaled_beta2_are_listed_and_conditionally_excepted(name):
    assert kinds(name) == {("S3", "prohibited"), ("S3", "exception")}


@pytest.mark.parametrize("name,section", [
    ("testosterone", "S1"), ("nandrolone", "S1"), ("clenbuterol", "S1"), ("darbepoetins", "S2"),
    ("anastrozole", "S4"), ("tamoxifen", "S4"), ("meldonium", "S4"), ("furosemide", "S5"),
    ("hydrochlorothiazide", "S5"), ("sibutramine", "S6"), ("4-methylhexan-2-amine", "S6"),
    ("morphine", "S7"), ("prednisolone", "S9"), ("dexamethasone", "S9"), ("propranolol", "P1"),
])
def test_prohibited_substances_in_right_section(name, section):
    assert (section, "prohibited") in kinds(name)


def test_p1_sports_exclude_weightlifting():
    sports = " ".join(LIST["sections"]["P1"]["sports"]).lower()
    assert "archery" in sports and "weightlifting" not in sports


def test_p1_sports_complete_with_out_of_competition_marks():
    """원문 20쪽: 종목 8개, * 표시(경기기간 외에도 금지) 3개."""
    p1 = LIST["sections"]["P1"]
    assert len(p1["sports"]) == 8 and any("Shooting" in s for s in p1["sports"]) and any("Underwater" in s for s in p1["sports"])
    assert sorted(s.split(" ")[0] for s in p1["sports_out_of_competition"]) == ["Archery", "Shooting", "Underwater"]


def test_no_sentence_fragments_as_items():
    bad = [i["name"] for i in LIST["items"] if i["name"].lower().startswith(("and other", "including", "such as", "but not", "its ", "their "))
           or NOT_A_NAME.search(i["name"]) or i["name"].count(" ") > 8]
    assert bad == []


# 이름에 남으면 조회가 깨지는 흔적: 닫는 괄호 꼬리, 제로폭 공백, 분류 꼬리 문구, 문장 조각
NOT_A_NAME = re.compile(r"^[^(\[]*[)\]]|[\u200b\u200c\u200d\ufeff]| and (its|their) | such as\b|\bbut not limited")


@pytest.mark.parametrize("field", ["synonyms"])
def test_no_broken_synonyms(field):
    bad = [(i["name"], s) for i in LIST["items"] for s in i[field] if NOT_A_NAME.search(s) or s.lower().startswith("e.g.")]
    assert bad == []


# ---------- 금지방법(M1–M3)과 S0: 손 보정 (knowledge/drugs/wada/processed/wada_manual_2026.yaml) ----------

def test_methods_are_prohibited_at_all_times_not_exceptions():
    """독립 검토에서 M1–M3 내용이 S5 '예외'로 들어가 앱이 '조건부'로 보여준 결함의 회귀 방지."""
    methods = [i for i in LIST["items"] if i["section"] in ("M1", "M2", "M3")]
    assert {i["section"] for i in methods} == {"M1", "M2", "M3"}
    assert all(i["kind"] == "prohibited" and i["prohibited"] == "all_times" for i in methods)
    for name in ["perfluorochemicals", "efaproxiral", "voxelotor", "gene silencing", "intravenous infusion"]:
        assert kinds(name) and all(sec.startswith("M") and k == "prohibited" for sec, k in kinds(name)), name


def test_s5_has_exactly_the_five_listed_exceptions():
    ex = sorted(i["name"].lower() for i in LIST["items"] if i["section"] == "S5" and i["kind"] == "exception")
    assert ex == ["brinzolamide", "dorzolamide", "drospirenone", "felypressin", "pamabrom"]


@pytest.mark.parametrize("name", ["BPC-157", "DNP", "S-107", "ARM210", "reldesemtiv", "tirasemtiv"])
def test_s0_named_substances(name):
    assert kinds(name) == {("S0", "prohibited")}


@pytest.mark.parametrize("name,section", [
    ("cathinone", "S6"), ("prolintane", "S6"), ("1,3-dimethylbutylamine", "S6"), ("1,4-DMAA", "S6"), ("MDMA", "S6"),
    ("kisspeptin", "S2"), ("gonadorelin", "S2"), ("tabimorelin", "S2"), ("GHRP-6", "S2"), ("CERA", "S2"), ("IGF-1", "S2"),
    ("enobosarm", "S1"), ("LGD-4033", "S1"), ("trestolone", "S1"), ("danazol", "S1"), ("elacestrant", "S4"),
    ("BAM15", "S4"), ("GW1516", "S4"), ("insulin", "S4"), ("fentanyl", "S7"), ("marijuana", "S8"), ("THC", "S8"),
])
def test_previously_missed_substances(name, section):
    """독립 검토에서 UNKNOWN으로 빠졌던 이름(괄호 꼬리, e.g. 앞 머리, 숫자로 시작, 글머리 뒤 문단 등)."""
    assert (section, "prohibited") in kinds(name)


def test_s9_route_words_are_not_items():
    assert not kinds("buccal") and not kinds("dermal")


def test_section_notes_kept():
    sc = LIST["section_conditions"]
    assert "1000 ng/mL" in sc["S3"] and "이뇨제" in sc["S5"] and "구강점막" in sc["S9"]


# ---------- 원문 INDEX 전수 ----------

PAGE_SECTION = {4: "S0", 5: "S1", 6: "S1", 7: "S2", 8: "S2", 9: "S3", 10: "S4", 11: "S4", 12: "S5", 13: "M", 14: "M",
                15: "S6", 16: "S6", 17: "S7", 18: "S8", 19: "S9", 20: "P1"}


def _variants(term: str) -> list[str]:
    """INDEX 표기 "Growth hormone (GH)" → 전체, 괄호 뺀 것, 괄호 앞, 괄호 안."""
    v = [term, re.sub(r"\s*\([^()]*\)\s*", " ", term).strip(), re.split(r"\s*\(", term)[0], *re.findall(r"\(([^()]*)\)", term)]
    return [x for x in dict.fromkeys(v) if x]


def test_index_extracted():
    assert len(LIST["index"]) >= 500 and all(e["pages"] for e in LIST["index"])


def test_every_index_term_resolves_to_its_own_section():
    """원문 INDEX의 모든 표제어가 앱에서 조회되고, 표제어 쪽의 섹션과 같은 섹션으로 판정되는지.
    제외는 index_not_substances(방법 설명 단어 등)에 이유와 함께 적은 것만."""
    from app.drugs import substances

    skip = LIST["index_not_substances"]
    assert all(t in {e["term"] for e in LIST["index"]} for t in skip)  # 제외 목록에 오타·옛 표제어가 남지 않게
    misses = []
    for e in LIST["index"]:
        if e["term"] in skip:
            continue
        for q in _variants(e["term"]):
            r = substances.check(q, "KR", "in_competition")
            if r.matched_kind == "substance" and r.status != "UNKNOWN":
                break
        else:
            misses.append((e["term"], "조회 안 됨")); continue
        sections = {PAGE_SECTION[p] for p in e["pages"]}
        got = {("M" if c.startswith("M") else c.split(".")[0]) for i in r.ingredients if (c := i.wada_class)}
        # 손 조회표가 우선하는 성분(wada_class 없음)은 판정 상태만 본다: 모니터링·P1·CBD → 확인 필요
        if got and not got & sections:
            misses.append((e["term"], f"섹션 {sorted(got)} ≠ 원문 {sorted(sections)}"))
    assert misses == []


def test_at_all_times_index_terms_never_under_classified():
    """상시 금지 섹션(S0–S5, M)의 INDEX 표제어는 경기기간 외에도 금지로 나와야 한다.
    예외는 원문에 이름이 적힌 예외·기준치 성분뿐."""
    from app.drugs import substances

    allowed = {"brinzolamide", "dorzolamide", "drospirenone", "felypressin", "pamabrom",  # S5 예외
               "salbutamol", "formoterol", "salmeterol", "vilanterol",  # S3 흡입 예외(용량)
               "cathine", "ephedrine", "methylephedrine", "pseudoephedrine"}  # S5 NOTE에 나오는 S6 기준치 성분
    bad = []
    for e in LIST["index"]:
        if e["term"] in LIST["index_not_substances"] or PAGE_SECTION[e["pages"][0]] not in ("S0", "S1", "S2", "S3", "S4", "S5", "M"):
            continue
        for q in _variants(e["term"]):
            r = substances.check(q, "KR", "out_of_competition")
            if r.matched_kind == "substance" and r.status != "UNKNOWN":
                break
        if r.status != "PROHIBITED" and e["term"].lower() not in allowed:
            bad.append((e["term"], r.status))
    assert bad == []
