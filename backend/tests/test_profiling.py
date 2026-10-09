"""교육 프로파일 계산 (D4, D5, D6, D25, D26). 선수 직접 입력과 데모 예시가 같은 경로를 탄다."""

import json

import pytest

from app import profiling
from app.config import DATA
from app.profiles import load_team_summary
from app.schemas import ComputeRequest, TeamSummaryRecord

EXAMPLES = json.loads((DATA / "demo_examples.json").read_text(encoding="utf-8"))
EXPECTED = {"A": ["rapid_improvement"], "B": ["decline"], "C": ["weight_change"], "D": ["high_level"],
            "E": ["baseline"]}


def request(aid: str, **changes) -> ComputeRequest:
    return ComputeRequest(**{**EXAMPLES[aid], **changes})


@pytest.mark.parametrize("aid", list(EXPECTED))
def test_demo_examples_give_designed_tags(aid):
    """§2: 페르소나 하나에 표의 행 하나. 화면의 "입력 예시 채우기"와 같은 경로."""
    profile, prompt = profiling.compute(request(aid))
    assert profile.tags == EXPECTED[aid]
    assert prompt.tags == EXPECTED[aid]
    assert len(profile.forecast) == len(profile.records) - 2  # 예측은 직전 기록 2개 이상부터


def test_examples_fit_input_limits():
    for ex in EXAMPLES.values():
        assert 3 <= len(ex["records"]) <= 10


def test_result_does_not_depend_on_server_clock():
    """'최근' 창은 마지막 입력 날짜 기준이다. 모든 날짜를 2년 뒤로 옮겨도 태그와 이유가 같다(Figure 재현성)."""
    for aid in EXPECTED:
        ex = EXAMPLES[aid]
        shifted = [{**r, "date": f"{int(r['date'][:4]) - 2}{r['date'][4:]}"} for r in ex["records"]]
        a, _ = profiling.compute(request(aid))
        b, _ = profiling.compute(request(aid, records=shifted))
        assert (a.tags, [r.text for r in a.reasons]) == (b.tags, [r.text for r in b.reasons])


def test_too_few_rows_can_hide_a_weight_class_change():
    """C의 체급 변경은 약 15개월 전이라 최근 5행만 넣으면 이전 체급이 보이지 않는다 → 예시는 8행."""
    ex = EXAMPLES["C"]
    profile, _ = profiling.compute(request("C", records=ex["records"][-5:]))
    assert "weight_change" not in profile.tags


@pytest.mark.parametrize("sex,bw,expected", [("M", 73.0, 73), ("M", 73.1, 81), ("M", 109.0, 109), ("M", 110.0, 999),
                                             ("F", 45.0, 45), ("F", 87.1, 999), ("F", 30.0, 45)])
def test_weight_class_is_derived_from_body_weight(sex, bw, expected):
    assert profiling.weight_class(sex, bw) == expected


def test_prompt_profile_has_only_d15_fields():
    _, prompt = profiling.compute(request("A"))
    assert set(prompt.model_dump()) == {"tags", "age_band", "competition_level"}
    assert prompt.age_band == "18-20세"


def test_no_warnings_for_clean_examples():
    for aid in EXPECTED:
        assert profiling.validate(request(aid)) == []


def test_typo_jump_is_flagged_before_tagging():
    """D7: 오타 하나가 '급격한 향상' 태그를 만들지 않도록, 직전 대비 ±25%를 넘으면 확인을 요청한다."""
    rows = [dict(r) for r in EXAMPLES["E"]["records"]]
    rows[-1]["clean_jerk"] += 100
    warnings = profiling.validate(request("E", records=rows))
    assert [(w.row, w.code) for w in warnings if w.code == "jump"] == [(len(rows) - 1, "jump")]


def test_ratio_outside_range_is_flagged():
    rows = [dict(r) for r in EXAMPLES["E"]["records"]]
    rows[0]["snatch"], rows[0]["clean_jerk"] = 200, 100
    assert any(w.row == 0 and w.code == "ratio" for w in profiling.validate(request("E", records=rows)))


def test_params_are_marked_synthetic():
    """D26: 합성 파라미터로는 시범 모드가 뜨지 않는다. 실제 기록으로 다시 학습하면 "real"."""
    assert profiling.params_source() == "synthetic"
    assert profiling.params()["weight_class_system"] == "IWF-2018"


def test_no_rank_or_birth_year_in_outputs():
    """D8·§10: 순위 관련 값과 생년은 어떤 산출물에도 없다."""
    for name in ("demo_examples.json", "model_params.json", "team_summary.json"):
        raw = (DATA / name).read_text(encoding="utf-8")
        for word in ("percentile", "rank", "birth_year"):
            assert word not in raw, (name, word)


def test_demo_team_summary_has_topics_only():
    """D9: 이름·인원수 없음, 카탈로그 고정 순서."""
    rows = json.loads((DATA / "team_summary.json").read_text(encoding="utf-8"))
    for row in rows:
        TeamSummaryRecord.model_validate(row)
        assert set(row) == {"team_id", "topics"}
    assert len(load_team_summary("demo-team").topics) == 5
