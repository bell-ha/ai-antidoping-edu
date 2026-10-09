"""경기력 예측 (D4). 지금은 단순 추세 모델이고, 나중에 LSTM으로 교체한다.

인터페이스는 교체 후에도 같다:
    model = TrendModel.fit(background)
    model.predict(athlete, upto) -> Prediction(mean, lo, hi, sigma)

추세 모델 = 성별 연령 곡선(기준 합계 대비 비율, 2차식) + 선수 개인 오프셋(직전 최대 4개 대회 잔차 평균).
예측 구간 = 학습셋 체급별 한 걸음 앞 예측 잔차의 σ × 1.96 (그림 3(a) "체급별 잔차 분포"와 연결).
"""

from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from make_synthetic import CLASS_PEAK, Athlete

Z95 = 1.96
MIN_HISTORY = 2
OFFSET_WINDOW = 4


@dataclass
class Prediction:
    mean: float
    lo: float
    hi: float
    sigma: float


class TrendModel:
    def __init__(self, curves: dict[str, np.ndarray]):
        self.curves = curves
        self.sigma: dict[tuple[str, int], float] = {}

    @classmethod
    def fit(cls, athletes: list[Athlete]) -> "TrendModel":
        by_sex = defaultdict(lambda: ([], []))
        for a in athletes:
            for r in a.records:
                ages, ratios = by_sex[a.sex]
                ages.append(a.age_at(r.year))
                ratios.append(r.total / CLASS_PEAK[a.sex][r.weight_class])
        model = cls({sex: np.polyfit(ages, ratios, 2) for sex, (ages, ratios) in by_sex.items()})

        residuals = defaultdict(list)
        for a in athletes:
            for i in range(MIN_HISTORY, len(a.records)):
                r = a.records[i]
                residuals[(a.sex, r.weight_class)].append(r.total - model._mean(a, i))
        model.sigma = {key: float(np.std(v)) for key, v in residuals.items()}
        return model

    def _ratio(self, sex: str, age: float) -> float:
        return float(np.polyval(self.curves[sex], age))

    def _mean(self, a: Athlete, upto: int, year: int | None = None, weight_class: int | None = None) -> float:
        """records[:upto]만 보고 records[upto](또는 지정한 다음 대회)의 합계를 예측."""
        history = a.records[max(0, upto - OFFSET_WINDOW):upto]
        offset = np.mean([r.total / CLASS_PEAK[a.sex][r.weight_class] - self._ratio(a.sex, a.age_at(r.year))
                          for r in history])
        target = a.records[upto] if upto < len(a.records) else None
        year = year if year is not None else target.year
        weight_class = weight_class if weight_class is not None else target.weight_class
        return (self._ratio(a.sex, a.age_at(year)) + offset) * CLASS_PEAK[a.sex][weight_class]

    def predict(self, a: Athlete, upto: int, year: int | None = None, weight_class: int | None = None) -> Prediction:
        if upto < MIN_HISTORY:
            raise ValueError("예측에는 대회 기록이 최소 2개 필요합니다")
        mean = self._mean(a, upto, year, weight_class)
        wc = weight_class if weight_class is not None else a.records[min(upto, len(a.records) - 1)].weight_class
        sigma = self.sigma[(a.sex, wc)]
        return Prediction(mean, mean - Z95 * sigma, mean + Z95 * sigma, sigma)
