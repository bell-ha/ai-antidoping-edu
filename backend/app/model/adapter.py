"""연구진 경기력 모델 결과 → 플랫폼 (D32, D35).

플랫폼은 모델을 학습하지 않고 결과만 쓴다. 결과 모양은 연구진 인계본의 profile() 반환값을 따른다:
예측 합계, 관측 합계, 관측 − 예측, 기록 수, 경고. 예측 구간은 주지 않는다.

지금은 연구진 bundle이 없어 임시 모델(app.model.predict)로 채운다. bundle이 오면 `result()` 안에서
연구진 runtime(`APPModel(bundle).profile(request)`)을 부르고 그 값을 그대로 옮기면 된다 — 단계·교육은 이 모양만 본다.
"""

from app.model import predict
from app.schemas import ModelResult, ModelValue, ObservedValue

SOURCE = {"synthetic_trend": "synthetic", "rnn": "platform_temporary", "none": "none"}


def result(sex: str, birth_year: int, rows: list) -> ModelResult:
    """마지막 대회를 그 전 기록들로 예측한 결과. 모델이 없거나 기록이 모자라면 숫자 없이 경고만.
    rows: 날짜 오름차순 대회 기록(date, competition_category, body_weight, snatch, clean_jerk)."""
    p = predict.params()
    model = predict.model_for(sex, p)
    version = {"synthetic_trend": "synthetic_trend", "rnn": f"platform-temporary-rnn-{sex}", "none": "none"}[model]
    if not rows:
        return ModelResult(model_version=version, source=SOURCE[model], observed=ObservedValue(value=None), history_count=0,
                           prediction=ModelValue(value=None), residual_observed_minus_predicted=None,
                           data_warnings=["대회 기록이 없어요."])
    records = predict.to_records(sex, rows)
    upto = len(records) - 1
    base = dict(model_version=version, source=SOURCE[model], observed=ObservedValue(value=records[-1].total), history_count=upto)
    if model == "none":
        return ModelResult(**base, prediction=ModelValue(value=None), residual_observed_minus_predicted=None,
                           data_warnings=["이 성별은 연구진 경기력 모델이 아직 없어요."])
    if upto < p["min_history"]:
        return ModelResult(**base, prediction=ModelValue(value=None), residual_observed_minus_predicted=None,
                           data_warnings=[f"예측에는 이전 대회 기록이 {p['min_history']}개 이상 필요해요."])
    record_ages = predict.ages(birth_year, records)
    # 연구진 runtime처럼 모델이 낸 값 그대로(체급별 보정·구간은 넣지 않는다)
    if model == "rnn":
        value = predict.rnn_mean(p["files"][sex], records, record_ages, upto)
    else:
        value = predict.mean_prediction(sex, records, record_ages, upto, p)
    warnings = []
    if records[-1].competition_category == "domestic":
        warnings.append("국내 대회는 연구진 모델의 학습 자료에 없어 예측이 덜 정확할 수 있어요.")
    return ModelResult(**base, prediction=ModelValue(value=round(value, 1)),
                       residual_observed_minus_predicted=round(records[-1].total - value, 1), data_warnings=warnings)
