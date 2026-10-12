"""WADA 금지목록 자동 추출본(data/wada/prohibited_list_2026.json) 고정 테스트.

원문(2026 금지목록 PDF)에서 직접 확인한 분류를 고정한다. 특히 "금지 아님"인 예외가 금지로 바뀌지 않는지.
추출 스크립트: analysis/wada_extract.py
"""

import json
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[2] / "data/wada/prohibited_list_2026.json"
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


def test_no_sentence_fragments_as_items():
    bad = [i["name"] for i in LIST["items"] if i["name"].lower().startswith(("and other", "including", "such as"))
           or len(i["name"]) > 70]
    assert bad == []
