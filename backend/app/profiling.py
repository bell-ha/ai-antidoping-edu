"""교육 프로파일 계산 (D4, D5, D6, D25). 선수가 입력한 기록 → 예측 → 규칙 태그 → 추천.

analysis/(오프라인)는 모집단 파라미터를 학습해 data/model_params.json으로 내보내고, 추론과 규칙은 이 모듈
하나만 쓴다. 서버도 analysis/export.py(페르소나·데모 예시)도 여기를 import한다 — 코드 중복 금지.
순수 파이썬이다(numpy·torch 없음, D2).

예측 = 성별 연령 곡선(체급 기준 합계 대비 비율, 2차식) + 개인 오프셋(직전 최대 4개 대회 잔차 평균).
예측 구간 = 체급별 한 걸음 앞 예측 잔차 σ × 1.96.
'최근' 창(12·18개월)은 서버 시계가 아니라 **입력된 마지막 대회 날짜**를 기준으로 잰다 — 같은 입력이면
언제 계산해도 같은 결과(Figure 재현성).
"""

import json
from dataclasses import dataclass
from functools import cache

import yaml

from app.config import DATA, ROOT
from app.profiles import recommendation, tag_label
from app.schemas import AthleteProfile, ComputeRequest, ForecastPoint, InputWarning, PromptProfile, Reason, RecordPoint

TOP_CLASS = 999  # 최상위 무제한 체급(+109 / +87)
RATIO_RANGE = (0.35, 0.55)  # 인상/합계가 이 밖이면 입력 확인 경고
JUMP = 0.25  # 직전 대비 합계 변화가 이보다 크면 입력 확인 경고


@cache
def params() -> dict:
    return json.loads((DATA / "model_params.json").read_text(encoding="utf-8"))


@cache
def _rules() -> dict:
    return yaml.safe_load((ROOT / "knowledge/rules.yaml").read_text(encoding="utf-8"))


def params_source() -> str:
    """D26: "synthetic"이면 시범(DEMO_MODE=0)에서 서버가 시작을 거부한다."""
    return params()["source"]


def weight_class(sex: str, body_weight: float, classes: dict | None = None) -> int:
    """2018 IWF 체급. 계체 체중 이하인 가장 가벼운 체급 상한, 넘으면 최상위 체급."""
    limits = (classes or params()["classes"])[sex]
    return next((c for c in limits if c != TOP_CLASS and body_weight <= c), TOP_CLASS)


def age_band(age: int) -> str:
    if age < 18:
        return "18세 미만"
    if age < 21:
        return "18-20세"
    if age < 25:
        return "21-24세"
    return f"{age // 5 * 5}-{age // 5 * 5 + 4}세"


def _month_index(date: str) -> int:
    year, month = date.split("-")
    return int(year) * 12 + int(month) - 1


@dataclass(frozen=True)
class Record:
    """계산용 기록. 입력(RecordInput)이든 합성 데이터든 이 모양으로 바꿔 넣는다."""
    date: str
    competition_level: str
    weight_class: int
    body_weight: float
    snatch: int
    clean_jerk: int

    @property
    def total(self) -> int:
        return self.snatch + self.clean_jerk


@dataclass(frozen=True)
class Prediction:
    mean: float
    lo: float
    hi: float
    sigma: float


def ages(age_at_last: int, records: list[Record]) -> list[int]:
    """나이는 '마지막 대회 시점'으로 받는다. 기록별 나이 = age − (마지막 해 − 그 해)."""
    last_year = int(records[-1].date[:4])
    return [age_at_last - (last_year - int(r.date[:4])) for r in records]


def _ratio(sex: str, age: float, p: dict) -> float:
    a, b, c = p["curves"][sex]
    return a * age * age + b * age + c


def mean_prediction(sex: str, records: list[Record], record_ages: list[int], upto: int, p: dict | None = None) -> float:
    """records[:upto]만 보고 records[upto]의 합계를 예측. analysis가 σ를 학습할 때도 이 함수를 쓴다."""
    p = p or params()
    peak = p["class_peak"][sex]
    history = range(max(0, upto - p["offset_window"]), upto)
    offset = sum(records[i].total / peak[str(records[i].weight_class)] - _ratio(sex, record_ages[i], p)
                 for i in history) / len(history)
    target = records[upto]
    return (_ratio(sex, record_ages[upto], p) + offset) * peak[str(target.weight_class)]


def predict(sex: str, records: list[Record], record_ages: list[int], upto: int, p: dict | None = None) -> Prediction:
    p = p or params()
    if upto < p["min_history"]:
        raise ValueError("예측에는 대회 기록이 최소 2개 필요합니다")
    mean = mean_prediction(sex, records, record_ages, upto, p)
    sigma = p["sigma"][f"{sex}{records[upto].weight_class}"]
    return Prediction(mean, mean - p["z95"] * sigma, mean + p["z95"] * sigma, sigma)


@dataclass(frozen=True)
class Result:
    tags: list[str]
    reasons: list[Reason]
    recommendations: list[str]
    forecast: list[ForecastPoint]


def evaluate(sex: str, age_at_last: int, records: list[Record], emphasis_first: bool = False,
             p: dict | None = None) -> Result:
    """규칙 = knowledge/rules.yaml, 표의 행 순서대로 태그를 붙인다(D5). 추천 이유는 규칙 입력값 그대로(D6).

    emphasis_first: D8 — 동일 성별·체급·연령대 분포상 강조 구간일 때만 호출 쪽이 True로 넘긴다.
    그 판단에는 실데이터 모집단 분포가 필요하므로 입력 경로는 항상 False다.
    """
    p = p or params()
    rules = _rules()
    t = rules["thresholds"]
    record_ages = ages(age_at_last, records)
    last_i = len(records) - 1
    last = records[last_i]
    pred = predict(sex, records, record_ages, last_i, p)
    z = (last.total - pred.mean) / pred.sigma
    end = _month_index(last.date)

    def months_ago(r: Record) -> int:
        return end - _month_index(r.date)

    tags: list[str] = []
    reasons: list[Reason] = []

    def add(tag: str, text: str) -> None:
        tags.append(tag)
        reasons.append(Reason(tag=tag, text=text))

    if z >= t["residual_z_up"]:
        add("rapid_improvement", f"최근 기록이 예측보다 {z:+.1f}σ 높음 (기준 +{t['residual_z_up']:.1f}σ)")
    if z <= t["residual_z_down"]:
        add("decline", f"최근 기록이 예측보다 {z:+.1f}σ 낮음 (기준 {t['residual_z_down']:.1f}σ)")

    window = t["weight_class_window_months"]
    recent = [r for r in records if months_ago(r) <= window]
    earlier = [r for r in records if months_ago(r) > window]
    year_ago = [r for r in records if months_ago(r) >= 12]
    class_changed = bool(earlier) and any(r.weight_class != earlier[-1].weight_class for r in recent)
    bw_change = (last.body_weight / year_ago[-1].body_weight - 1) * 100 if year_ago else 0.0
    if class_changed:
        before = earlier[-1]
        add("weight_change", f"최근 {window}개월 안에 체급 {before.weight_class}→{last.weight_class}kg "
                             f"(체중 {before.body_weight}→{last.body_weight}kg)")
    elif abs(bw_change) >= t["body_weight_change_pct"]:
        add("weight_change", f"최근 12개월 체중 {bw_change:+.1f}% (기준 ±{t['body_weight_change_pct']:.0f}%)")

    if any(r.competition_level == "international" for r in records if months_ago(r) <= t["high_level_window_months"]):
        add("high_level", f"최근 {t['high_level_window_months']}개월 안에 국제대회 출전")

    if not tags:
        add("baseline", f"최근 기록이 예측 범위 안 ({z:+.1f}σ, 기준 ±{t['residual_z_up']:.1f}σ)")

    recommendations: list[str] = []
    for tag in tags:
        contents = list(rules["tags"][tag]["contents"])
        first = rules["tags"][tag].get("emphasis_first")
        if first and emphasis_first:
            contents.remove(first)
            contents.insert(0, first)
        recommendations += [c for c in contents if c not in recommendations]

    forecast = []
    for i in range(p["min_history"], len(records)):
        f = predict(sex, records, record_ages, i, p)
        forecast.append(ForecastPoint(date=records[i].date, mean=round(f.mean, 1), lo=round(f.lo, 1), hi=round(f.hi, 1)))
    return Result(tags, reasons, recommendations, forecast)


def to_records(req: ComputeRequest) -> list[Record]:
    return [Record(r.date, r.competition_level, weight_class(req.sex, r.body_weight), r.body_weight, r.snatch,
                   r.clean_jerk) for r in req.records]


def validate(req: ComputeRequest) -> list[InputWarning]:
    """소프트 경고만(하드 오류는 schemas의 pydantic 검증). 오타 하나가 태그를 만들지 않도록, 태그 계산 전에
    사람이 한 번 확인하게 한다(D7)."""
    warnings: list[InputWarning] = []
    lo, hi = RATIO_RANGE
    for i, r in enumerate(req.records):
        ratio = r.snatch / (r.snatch + r.clean_jerk)
        if not lo <= ratio <= hi:
            warnings.append(InputWarning(row=i, field="snatch", code="ratio",
                                         message="인상과 용상의 비율이 일반적인 범위를 벗어나요. 입력을 다시 확인해 주세요."))
    for i in range(1, len(req.records)):
        before = req.records[i - 1].snatch + req.records[i - 1].clean_jerk
        now = req.records[i].snatch + req.records[i].clean_jerk
        if abs(now / before - 1) > JUMP:
            warnings.append(InputWarning(row=i, field="total", code="jump",
                                         message=f"직전 대회보다 합계가 {now - before:+d}kg 달라요. 이 기록이 맞나요?"))
    return warnings


def compute(req: ComputeRequest) -> tuple[AthleteProfile, PromptProfile]:
    """입력 → API 형태 프로파일 + 세션에 넣을 최소 정보(D15: 태그·연령대·경기 수준만). 저장하지 않는다."""
    records = to_records(req)
    result = evaluate(req.sex, req.age, records)
    last = records[-1]
    profile = AthleteProfile(
        athlete_id="self",
        sport="weightlifting",
        sex=req.sex,
        age=req.age,
        weight_class=last.weight_class,
        competition_level=last.competition_level,
        records=[RecordPoint(date=r.date, competition_level=r.competition_level, weight_class=r.weight_class,
                             body_weight=r.body_weight, snatch=r.snatch, clean_jerk=r.clean_jerk, total=r.total)
                 for r in records],
        forecast=result.forecast,
        tags=result.tags,
        tag_labels=[tag_label(t) for t in result.tags],
        reasons=result.reasons,
        recommendations=[recommendation(c) for c in result.recommendations],
    )
    return profile, PromptProfile(tags=result.tags, age_band=age_band(req.age), competition_level=last.competition_level)
