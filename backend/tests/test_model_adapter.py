"""연구진 모델 결과 모양 (D32, D35)."""

from types import SimpleNamespace as R

from app.model import adapter, predict

CONTRACT = {"model_version", "source", "prediction", "observed", "residual_observed_minus_predicted", "history_count",
            "prediction_interval_kg", "data_warnings"}


def rows(totals, category="world"):
    return [R(date=f"2025-{i + 1:02d}", competition_category=category, body_weight=72.5, snatch=round(t * 0.45),
              clean_jerk=t - round(t * 0.45)) for i, t in enumerate(totals)]


def test_has_every_contract_field_and_no_interval():
    r = adapter.result("M", 2000, rows([250, 255, 260, 265]))
    assert CONTRACT <= set(r.model_dump()) and r.prediction_interval_kg is None


def test_residual_is_observed_minus_predicted_on_last_record():
    r = adapter.result("M", 2000, rows([250, 255, 260, 300]))
    assert r.observed.value == 300 and r.residual_observed_minus_predicted == round(300 - r.prediction.value, 1)
    assert r.history_count == 3


def test_too_few_records_gives_no_number():
    r = adapter.result("M", 2000, rows([250]))
    assert r.prediction.value is None and r.residual_observed_minus_predicted is None and r.data_warnings


def test_no_records():
    assert adapter.result("M", 2000, []).observed.value is None


def test_domestic_last_competition_warns():
    r = adapter.result("M", 2000, rows([250, 255, 260, 265], category="domestic"))
    assert any("국내" in w for w in r.data_warnings)


def test_weight_class_is_derived_from_body_weight():
    assert predict.weight_class("M", 72.5) == 73 and predict.weight_class("M", 130) == predict.TOP_CLASS
