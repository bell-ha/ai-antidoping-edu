"""합성 역도 경기력 데이터 (D5, D22). seed 고정, 2018 IWF 체급.

배경 선수는 예측 모델(predict.py)의 연령 곡선과 체급별 잔차 σ를 맞추는 데만 쓰고 화면에는 나오지 않는다.
페르소나 A~E는 추천 표의 행 하나씩에 대응하도록 사건을 주입한다(DESIGN-DECISIONS §2).
실제 데이터로 바꿀 때는 이 파일만 교체하고 Athlete/Record 모양은 유지한다.
"""

from dataclasses import dataclass, field

import numpy as np

SEED = 20261008
TODAY = (2026, 10)  # 재현성을 위해 "오늘"을 고정
COMPETITION_MONTHS = (3, 6, 9)
FIRST_YEAR = 2019

# 2018 IWF 체급. 999 = 최상위 무제한 체급(+109, +87)
CLASSES = {
    "M": [55, 61, 67, 73, 81, 89, 96, 102, 109, 999],
    "F": [45, 49, 55, 59, 64, 71, 76, 81, 87, 999],
}
# 체급별 기준 합계(kg). 국내 상위권 수준의 대략값이며 실제 기록이 아니다.
CLASS_PEAK = {
    "M": dict(zip(CLASSES["M"], [250, 270, 295, 315, 335, 350, 360, 365, 375, 400])),
    "F": dict(zip(CLASSES["F"], [160, 170, 185, 195, 205, 215, 220, 225, 230, 250])),
}


@dataclass
class Record:
    year: int
    month: int
    competition_level: str
    weight_class: int
    body_weight: float
    snatch: int
    clean_jerk: int
    total: int

    @property
    def date(self) -> str:
        return f"{self.year}-{self.month:02d}"


@dataclass
class Athlete:
    athlete_id: str
    sex: str
    birth_year: int
    records: list[Record] = field(default_factory=list)

    def age_at(self, year: int) -> int:
        return year - self.birth_year


def growth(age: float) -> float:
    """기준 합계 대비 비율. 14세 0.62에서 20대 후반 정점, 30세부터 연 1% 감소."""
    r = 0.62 + 0.38 * (1 - np.exp(-(age - 14) / 4))
    return r * (1 - 0.01 * max(0.0, age - 30))


def competition_dates(birth_year: int):
    for year in range(max(FIRST_YEAR, birth_year + 15), TODAY[0] + 1):
        for month in COMPETITION_MONTHS:
            if (year, month) < TODAY:
                yield year, month


def class_limit(weight_class: int, sex: str) -> float:
    return weight_class if weight_class != 999 else (124 if sex == "M" else 102)


def make_record(rng, sex, year, month, age, weight_class, talent, level, noise=0.025, factor=1.0, body_weight=None):
    total = CLASS_PEAK[sex][weight_class] * talent * growth(age) * factor * (1 + rng.normal(0, noise))
    total = int(round(total))
    snatch = int(round(total * rng.uniform(0.44, 0.46)))
    if body_weight is None:
        body_weight = class_limit(weight_class, sex) - rng.uniform(0.3, 2.5)
    return Record(year, month, level, weight_class, round(float(body_weight), 1), snatch, total - snatch, total)


def background(rng, n: int = 260) -> list[Athlete]:
    athletes = []
    for i in range(n):
        sex = "M" if i % 2 == 0 else "F"
        a = Athlete(f"bg{i:03d}", sex, int(rng.integers(1990, 2010)))
        weight_class = int(rng.choice(CLASSES[sex]))
        talent = float(np.clip(rng.normal(0.88, 0.06), 0.7, 1.05))
        for year, month in competition_dates(a.birth_year):
            age = a.age_at(year)
            level = "junior" if age < 18 else ("international" if talent > 0.97 else "national")
            a.records.append(make_record(rng, sex, year, month, age, weight_class, talent, level))
        if len(a.records) >= 4:
            athletes.append(a)
    return athletes


def personas(rng) -> list[Athlete]:
    """페르소나 하나에 신호 하나씩(§2). 노이즈를 작게 해 태그가 seed에 흔들리지 않게 한다."""
    n = 0.008
    out = []

    def build(aid, sex, birth_year, talent, plan):
        a = Athlete(aid, sex, birth_year)
        dates = list(competition_dates(birth_year))
        for idx, (year, month) in enumerate(dates):
            age = a.age_at(year)
            weight_class, level, factor, bw = plan(idx, len(dates), age)
            a.records.append(make_record(rng, sex, year, month, age, weight_class, talent, level, n, factor, bw))
        out.append(a)

    def junior_or(level):
        return lambda age: "junior" if age < 18 else level

    # A: 19세 남 73kg — 마지막 두 대회에서 급상승 → rapid_improvement
    build("A", "M", 2007, 0.90,
          lambda i, n_, age: (73, junior_or("national")(age), {n_ - 2: 1.05, n_ - 1: 1.11}.get(i, 1.0), None))
    # B: 27세 여 59kg — 부상 후 마지막 두 대회에서 하락 → decline
    build("B", "F", 1999, 0.92,
          lambda i, n_, age: (59, "national", {n_ - 2: 0.95, n_ - 1: 0.88}.get(i, 1.0), None))
    # C: 22세 남 81→89kg — 최근 다섯 번째 대회부터 체급 상향, 체중 약 9% 증가 → weight_change
    build("C", "M", 2004, 0.89,
          lambda i, n_, age: (89 if i >= n_ - 5 else 81, junior_or("national")(age), 1.0,
                              87.6 if i >= n_ - 5 else 80.2))
    # D: 25세 여 64kg 국가대표 — 최근 1년 국제대회 출전 → high_level
    build("D", "F", 2001, 0.97,
          lambda i, n_, age: (64, "international" if i >= n_ - 4 else "national", 1.0, None))
    # E: 23세 남 96kg — 변화 없음 → baseline (S3 비교 Figure의 대조군)
    build("E", "M", 2003, 0.88,
          lambda i, n_, age: (96, junior_or("national")(age), 1.0, 95.1))
    return out


def generate() -> tuple[list[Athlete], list[Athlete]]:
    rng = np.random.default_rng(SEED)
    return background(rng), personas(rng)
