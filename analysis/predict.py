"""모집단 파라미터 학습 (D4). 추론은 backend/app/profiling.py가 하고, 여기서는 그 추론에 쓸 숫자만 만든다.

  fit(background) -> model_params.json에 들어갈 dict
    curves     : 성별 연령 곡선(체급 기준 합계 대비 비율, 2차식 계수)
    class_peak : 체급별 기준 합계 — 합성 데이터 생성기의 값(실제 기록 아님)
    sigma      : 성별·체급별 한 걸음 앞 예측 잔차의 표준편차 (그림 3(a) "체급별 잔차 분포")
    source     : "synthetic" | "real" — 합성이면 시범 모드에서 서버가 시작을 거부한다(D26)

LSTM으로 바꿀 때는 이 파일과 profiling.mean_prediction을 함께 교체한다(인터페이스는 같게).
"""

from collections import defaultdict

import numpy as np

from app.profiling import TOP_CLASS, Record, ages, mean_prediction
from make_synthetic import CLASS_PEAK, CLASSES, Athlete

Z95 = 1.96
MIN_HISTORY = 2
OFFSET_WINDOW = 4


# 합성 생성기의 3단계 수준 → 폼 범주(데모 페르소나 D의 국제대회는 세계대회로 둔다)
CATEGORY = {"junior": "domestic", "national": "domestic", "international": "world"}


def to_records(a: Athlete) -> list[Record]:
    return [Record(r.date, CATEGORY[r.competition_level], r.weight_class, r.body_weight, r.snatch, r.clean_jerk)
            for r in a.records]


def fit(athletes: list[Athlete], source: str) -> dict:
    assert TOP_CLASS in CLASSES["M"] and TOP_CLASS in CLASSES["F"]
    by_sex = defaultdict(lambda: ([], []))
    for a in athletes:
        for r in a.records:
            xs, ys = by_sex[a.sex]
            xs.append(a.age_at(r.year))
            ys.append(r.total / CLASS_PEAK[a.sex][r.weight_class])
    params = {
        "source": source,
        "model": "synthetic_trend",
        "weight_class_system": "IWF-2018",
        "classes": CLASSES,
        "class_peak": {sex: {str(c): v for c, v in peaks.items()} for sex, peaks in CLASS_PEAK.items()},
        "curves": {sex: [float(c) for c in np.polyfit(xs, ys, 2)] for sex, (xs, ys) in sorted(by_sex.items())},
        "z95": Z95,
        "min_history": MIN_HISTORY,
        "offset_window": OFFSET_WINDOW,
    }

    residuals = defaultdict(list)
    for a in athletes:
        records = to_records(a)
        record_ages = ages(a.birth_year, records)
        for i in range(MIN_HISTORY, len(records)):
            residuals[f"{a.sex}{records[i].weight_class}"].append(
                records[i].total - mean_prediction(a.sex, records, record_ages, i, params))
    params["sigma"] = {key: round(float(np.std(v)), 3) for key, v in sorted(residuals.items())}
    return params
