"""교육 프로파일 계산 (D4, D5, D6, D25, D26). 선수 직접 입력과 데모 예시가 같은 경로를 탄다."""

import json

import numpy as np
import pytest

from app import profiling
from app.config import DATA, ROOT
from app.schemas import ComputeRequest

EXAMPLES = json.loads((DATA / "demo_examples.json").read_text(encoding="utf-8"))
PERSONAS = ["A", "B", "C", "D", "E"]  # 논문 Figure용 — 태그가 바뀌면 Figure가 바뀐다
REAL_MODELS = ROOT / "private/models"  # 레포 밖 실모델(gitignore). 없으면 rnn 기대값 테스트는 건너뜀


def request(aid: str, **changes) -> ComputeRequest:
    return ComputeRequest(**{**EXAMPLES[aid], **changes})


@pytest.mark.parametrize("aid", list(EXAMPLES))
def test_examples_give_hand_written_tags(aid):
    """페르소나(§2)와 테스트 시나리오: 손으로 적은 기대 태그·경고(analysis/scenarios.py)와 같아야 한다.
    화면의 "입력 예시 채우기"·"테스트 시나리오"와 같은 경로."""
    profile, prompt = profiling.compute(request(aid))
    assert profile.tags == prompt.tags == EXAMPLES[aid]["expect"]["synthetic_trend"]
    assert [w.code for w in profiling.validate(request(aid))] == EXAMPLES[aid]["warnings"]
    assert len(profile.forecast) == len(profile.records) - 2  # 예측은 직전 기록 2개 이상부터


def test_personas_keep_figure_tags():
    """Figure가 의존하는 페르소나 태그는 시나리오 정의를 바꾸다가 함께 바뀌면 안 된다."""
    assert {aid: EXAMPLES[aid]["expect"]["synthetic_trend"] for aid in PERSONAS} == {
        "A": ["rapid_improvement"], "B": ["decline"], "C": ["weight_change"], "D": ["high_level"], "E": ["baseline"]}


@pytest.mark.skipif(not (REAL_MODELS / "model_params.json").exists(), reason="실모델(private/models) 없음")
@pytest.mark.parametrize("aid", list(EXAMPLES))
def test_examples_with_real_model(aid, monkeypatch):
    """실데이터 RNN에서의 기대 태그. 실모델은 σ가 넓어 합성과 다를 수 있다(예: A)."""
    monkeypatch.setattr(profiling, "MODEL_DIR", REAL_MODELS)
    profiling.params.cache_clear()
    profiling._rnn.cache_clear()
    try:
        profile, _ = profiling.compute(request(aid))
        assert profile.tags == EXAMPLES[aid]["expect"]["rnn"]
        assert profile.model == ("none" if EXAMPLES[aid]["sex"] == "F" else "rnn")
    finally:
        profiling.params.cache_clear()
        profiling._rnn.cache_clear()


def test_examples_fit_input_limits():
    for ex in EXAMPLES.values():
        assert 3 <= len(ex["records"]) <= 10


def test_result_does_not_depend_on_server_clock():
    """'최근' 창은 마지막 입력 날짜 기준이다. 모든 날짜와 출생연도를 2년 앞으로 옮겨도(나이는 같음) 태그와
    이유가 같다(Figure 재현성)."""
    for aid in PERSONAS:
        ex = EXAMPLES[aid]
        shifted = [{**r, "date": f"{int(r['date'][:4]) - 2}{r['date'][4:]}"} for r in ex["records"]]
        a, _ = profiling.compute(request(aid))
        b, _ = profiling.compute(request(aid, records=shifted, birth_year=ex["birth_year"] - 2))
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
    assert set(prompt.model_dump()) == {"tags", "age_band", "competition_category"}
    assert prompt.age_band == "18-20세"


def test_no_warnings_for_clean_examples():
    for aid in PERSONAS:
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
    """D8·§10: 순위 관련 값은 어떤 산출물에도 없다. 출생연도는 합성 데모 입력(demo_examples)에만 있다."""
    for name in ("demo_examples.json", "model_params.json"):
        raw = (DATA / name).read_text(encoding="utf-8")
        for word in ("percentile", "rank") + (() if name == "demo_examples.json" else ("birth_year",)):
            assert word not in raw, (name, word)



def test_weight_jump_suppresses_performance_tags():
    """예측 모델에 체중 입력이 없어 체중을 늘린 선수의 잔차가 계통적으로 크다(OOF 실측) →
    직전 대비 체중 변화가 기준을 넘으면 급격한 향상·감소를 붙이지 않고 체중 변화로 둔다."""
    rows = [dict(r) for r in EXAMPLES["A"]["records"]]
    rows[-1]["body_weight"] = rows[-2]["body_weight"] + 6.0
    profile, _ = profiling.compute(request("A", records=rows))
    assert profile.tags == ["weight_change"]
    assert "체중" in profile.reasons[0].text


# ---------- rnn 경로 (실데이터 가중치는 레포에 없으므로 작은 무작위 모델로 경로만 검증) ----------

@pytest.fixture
def rnn_params(tmp_path, monkeypatch):
    rng = np.random.default_rng(0)
    h, d = 4, 1 + 2 + 2 + 2
    w = {"emb_ec.weight": rng.normal(size=(5, 2)), "emb_age.weight": rng.normal(size=(40, 2)),
         "emb_year.weight": rng.normal(size=(30, 2)), "rnn.weight_ih_l0": rng.normal(size=(4 * h, d)) * 0.1,
         "rnn.weight_hh_l0": rng.normal(size=(4 * h, h)) * 0.1, "rnn.bias_ih_l0": np.zeros(4 * h),
         "rnn.bias_hh_l0": np.zeros(4 * h), "head.0.weight": rng.normal(size=(2, h)), "head.0.bias": np.zeros(2),
         "head.3.weight": rng.normal(size=(1, 2)), "head.3.bias": np.zeros(1)}
    for k in ("emb_ec.weight", "emb_age.weight", "emb_year.weight"):
        w[k][0] = 0.0  # padding_idx
    np.savez(tmp_path / "rnn_M.npz", **w)
    classes = profiling.params()["classes"]
    meta = {"vocab": [{"continent": 1, "etc": 2, "nation": 3, "world": 4},
                      {str(a): i + 1 for i, a in enumerate(range(10, 49))},
                      {str(y): i + 1 for i, y in enumerate(range(1998, 2023))}],
            "center": 250.0, "scale": 40.0, "z95": 1.96,
            "bias": {f"M{c}": 5.0 for c in classes["M"]}, "sigma": {f"M{c}": 15.0 for c in classes["M"]}}
    (tmp_path / "rnn_M.json").write_text(json.dumps(meta), encoding="utf-8")
    p = {"source": "real", "model": "rnn", "classes": classes, "min_history": 2, "files": {"M": "rnn_M", "F": None}}
    monkeypatch.setattr(profiling, "MODEL_DIR", tmp_path)
    profiling._rnn.cache_clear()
    monkeypatch.setattr(profiling, "params", lambda: p)
    yield p
    profiling._rnn.cache_clear()


def test_rnn_path_applies_class_bias_and_sigma(rnn_params):
    from app import rnn_infer
    profile, _ = profiling.compute(request("E"))
    assert profile.model == "rnn"
    records = profiling.to_records(request("E"))
    record_ages = profiling.ages(EXAMPLES["E"]["birth_year"], records)
    raw = profiling._rnn_mean("rnn_M", records, record_ages, len(records) - 1)
    last = profile.forecast[-1]
    assert last.mean == pytest.approx(raw + 5.0, abs=0.06)
    assert last.hi - last.lo == pytest.approx(2 * 1.96 * 15.0, abs=0.2)
    assert rnn_infer is not None


def test_rnn_unseen_year_uses_zero_embedding(rnn_params):
    """학습 이후 연도(2023+)는 vocab 밖 → 0(영벡터). 데모 E의 기록(2024–2026)이 전부 그 경우다."""
    meta, _ = profiling._rnn("rnn_M")
    assert all(r["date"][:4] not in meta["vocab"][2] for r in EXAMPLES["E"]["records"])
    profile, _ = profiling.compute(request("E"))
    assert profile.model == "rnn" and len(profile.forecast) == len(EXAMPLES["E"]["records"]) - 2


def test_rnn_domestic_history_adds_notice(rnn_params):
    profile, _ = profiling.compute(request("E"))  # 데모 E는 국내 대회만
    assert profiling.DOMESTIC_NOTICE in profile.notices


def test_sex_without_model_returns_no_numbers(rnn_params):
    """인계 계약: 모델이 없으면 숫자 대신 상태. 예측이 필요한 태그는 없고 입력 기반 태그만."""
    profile, prompt = profiling.compute(request("B"))  # B는 여자, 여자 모델 없음
    assert profile.model == "none" and profile.forecast == []
    assert profiling.NO_MODEL_NOTICE in profile.notices
    assert not {"rapid_improvement", "decline"} & set(profile.tags)
    assert profile.tags == ["baseline"] and "예측 없이" in profile.reasons[0].text


def test_rule_checklist_covers_all_rules_without_scores():
    """판정 점검표: 4개 규칙 모두, 붙지 않은 것까지. 규칙 입력값과 기준만 — 위험·의심·점수 표현 없음(D7)."""
    for aid in EXAMPLES:
        profile, _ = profiling.compute(request(aid))
        assert [c.tag for c in profile.checks] == ["rapid_improvement", "decline", "weight_change", "high_level"]
        assert {c.tag for c in profile.checks if c.met} == set(profile.tags) - {"baseline"}
        for c in profile.checks:
            assert not any(word in c.detail for word in ("위험", "의심", "점수"))


def test_rule_checklist_explains_boundary_and_suppression():
    t03 = {c.tag: c for c in profiling.compute(request("T03"))[0].checks}
    assert not t03["weight_change"].met and "+5.0kg" in t03["weight_change"].detail
    t01 = {c.tag: c for c in profiling.compute(request("T01"))[0].checks}
    assert not t01["rapid_improvement"].met and "판단하지 않음" in t01["rapid_improvement"].detail
