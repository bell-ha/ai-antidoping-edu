"""교육 프로파일 계산 (D4, D5, D6, D25, D26). 선수가 입력한 기록 → 예측 → 규칙 태그 → 추천.

예측 모델은 MODEL_DIR(기본 data/)의 model_params.json이 정한다. 추론과 규칙은 이 모듈 하나만 쓰고, 서버도 analysis/(학습·데모
예시)도 여기를 import한다 — 코드 중복 금지. torch는 쓰지 않는다(D2).

  synthetic_trend : 합성 데이터로 학습한 추세 모델(데모·Figure). 성별 연령 곡선 + 개인 오프셋.
  rnn             : 연구진 RNN(LSTM)을 실제 기록으로 학습한 모델(analysis/train_rnn.py). numpy로 추론
                    (app.rnn_infer). 성별마다 파일이 따로 있고, 없는 성별은 예측하지 않는다(model "none").

예측값은 체급별 편향(OOF 평균 잔차)을 더한 값이고, 구간은 그 ± 1.96σ다. 그래서 z = (실제 − 예측) / σ.
'최근' 창(12·18개월)은 서버 시계가 아니라 **입력된 마지막 대회 날짜** 기준이다 — 같은 입력이면 언제
계산해도 같은 결과(Figure 재현성).
"""

import json
from dataclasses import dataclass
from functools import cache

import yaml

from app.config import MODEL_DIR, ROOT
from app.profiles import recommendation, tag_label
from app.schemas import (AthleteProfile, ComputeRequest, ForecastPoint, InputWarning, PromptProfile, Reason, RecordPoint,
                         RuleCheck)

TOP_CLASS = 999  # 최상위 무제한 체급(+109 / +87)
RATIO_RANGE = (0.35, 0.55)  # 인상/합계가 이 밖이면 입력 확인 경고
JUMP = 0.25  # 직전 대비 합계 변화가 이보다 크면 입력 확인 경고
# 폼 범주 → 연구진 모델의 event_category 토큰. 모델의 "nation"은 대회명 키워드 규칙상 국제 초청전이 대부분이고,
# 한국 국내 대회는 학습 자료에 없어 "etc"로 보낸다(범주별 예측 차이 실험은 private/ 근거 문서 참고).
EVENT_TOKEN = {"world": "world", "continent": "continent", "other_international": "nation", "domestic": "etc"}
NO_MODEL_NOTICE = "이 성별의 경기력 예측 모델이 아직 없어요. 기록 변화에 따른 추천 없이 기본 교육을 보여드려요."
DOMESTIC_NOTICE = "국내 대회는 예측 모델의 학습 자료(국제대회 기록)에 없어서, 예측이 덜 정확할 수 있어요."


@cache
def params() -> dict:
    return json.loads((MODEL_DIR / "model_params.json").read_text(encoding="utf-8"))


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
    competition_category: str
    weight_class: int
    body_weight: float
    snatch: int
    clean_jerk: int

    @property
    def total(self) -> int:
        return self.snatch + self.clean_jerk


@dataclass(frozen=True)
class Prediction:
    mean: float  # 편향 보정 후
    lo: float
    hi: float
    sigma: float


def ages(birth_year: int, records: list[Record]) -> list[int]:
    """연구진 모델과 같은 정의: 대회연도 − 출생연도."""
    return [int(r.date[:4]) - birth_year for r in records]


# ---------- synthetic_trend ----------

def _ratio(sex: str, age: float, p: dict) -> float:
    a, b, c = p["curves"][sex]
    return a * age * age + b * age + c


def mean_prediction(sex: str, records: list[Record], record_ages: list[int], upto: int, p: dict | None = None) -> float:
    """추세 모델: records[:upto]만 보고 records[upto]의 합계를 예측. analysis가 σ를 학습할 때도 이 함수를 쓴다."""
    p = p or params()
    peak = p["class_peak"][sex]
    history = range(max(0, upto - p["offset_window"]), upto)
    offset = sum(records[i].total / peak[str(records[i].weight_class)] - _ratio(sex, record_ages[i], p)
                 for i in history) / len(history)
    target = records[upto]
    return (_ratio(sex, record_ages[upto], p) + offset) * peak[str(target.weight_class)]


# ---------- rnn ----------

@cache
def _rnn(name: str) -> tuple[dict, dict]:
    from app import rnn_infer  # numpy는 rnn 경로에서만 필요하다
    meta = json.loads((MODEL_DIR / f"{name}.json").read_text(encoding="utf-8"))
    return meta, rnn_infer.load(MODEL_DIR / f"{name}.npz")


def _rnn_mean(name: str, records: list[Record], record_ages: list[int], upto: int) -> float:
    from app import rnn_infer
    meta, w = _rnn(name)
    ec_vocab, age_vocab, year_vocab = meta["vocab"]
    history = records[:upto]
    return rnn_infer.predict(
        w, meta["center"], meta["scale"], [r.total for r in history],
        rnn_infer.encode(ec_vocab, [EVENT_TOKEN[r.competition_category] for r in history]),
        rnn_infer.encode(age_vocab, [str(a) for a in record_ages[:upto]]),
        rnn_infer.encode(year_vocab, [r.date[:4] for r in history]))


def model_for(sex: str, p: dict | None = None) -> str:
    """"synthetic_trend" | "rnn" | "none"(그 성별의 모델 파일이 없음)."""
    p = p or params()
    if p.get("model", "synthetic_trend") == "synthetic_trend":
        return "synthetic_trend"
    return "rnn" if p["files"].get(sex) else "none"


def predict(sex: str, records: list[Record], record_ages: list[int], upto: int, p: dict | None = None) -> Prediction:
    p = p or params()
    if upto < p["min_history"]:
        raise ValueError("예측에는 대회 기록이 최소 2개 필요합니다")
    key = f"{sex}{records[upto].weight_class}"
    if model_for(sex, p) == "rnn":
        meta, _ = _rnn(p["files"][sex])
        mean = _rnn_mean(p["files"][sex], records, record_ages, upto) + meta["bias"][key]
        sigma, z95 = meta["sigma"][key], meta["z95"]
    else:
        mean = mean_prediction(sex, records, record_ages, upto, p)
        sigma, z95 = p["sigma"][key], p["z95"]
    return Prediction(mean, mean - z95 * sigma, mean + z95 * sigma, sigma)


# ---------- 규칙 ----------

@dataclass(frozen=True)
class Result:
    model: str
    tags: list[str]
    reasons: list[Reason]
    recommendations: list[str]
    forecast: list[ForecastPoint]
    notices: list[str]
    checks: list[RuleCheck]


def evaluate(sex: str, birth_year: int, records: list[Record], emphasis_first: bool = False,
             p: dict | None = None) -> Result:
    """규칙 = knowledge/rules.yaml, 표의 행 순서대로 태그를 붙인다(D5). 추천 이유는 규칙 입력값 그대로(D6).

    예측이 필요한 태그(급격한 향상·감소)는 그 성별의 모델이 있을 때만 붙인다. 체중 변화와 경기 수준은
    입력만으로 판단하므로 모델이 없어도 붙는다.
    emphasis_first: D8 — 동일 성별·체급·연령대 분포상 강조 구간일 때만 호출 쪽이 True로 넘긴다.
    그 판단에는 실데이터 모집단 분포가 필요하므로 입력 경로는 항상 False다.
    """
    p = p or params()
    rules = _rules()
    t = rules["thresholds"]
    model = model_for(sex, p)
    record_ages = ages(birth_year, records)
    last_i = len(records) - 1
    last = records[last_i]
    end = _month_index(last.date)
    notices: list[str] = []
    z = None
    if model != "none":
        pred = predict(sex, records, record_ages, last_i, p)
        z = (last.total - pred.mean) / pred.sigma
    else:
        notices.append(NO_MODEL_NOTICE)
    if model == "rnn" and any(r.competition_category == "domestic" for r in records[:last_i]):
        notices.append(DOMESTIC_NOTICE)

    def months_ago(r: Record) -> int:
        return end - _month_index(r.date)

    tags: list[str] = []
    reasons: list[Reason] = []

    def add(tag: str, text: str) -> None:
        tags.append(tag)
        reasons.append(Reason(tag=tag, text=text))

    # 예측 모델에 체중 입력이 없으므로, 직전 대회보다 체중이 크게 바뀌었으면 기록 변화를 판단하지 않는다.
    jump = last.body_weight - records[last_i - 1].body_weight
    weight_jumped = abs(jump) > t["weight_jump_kg"]
    if z is not None and not weight_jumped and z >= t["residual_z_up"]:
        add("rapid_improvement", f"최근 기록이 예측보다 {z:+.1f}σ 높음 (기준 +{t['residual_z_up']:.1f}σ)")
    if z is not None and not weight_jumped and z <= t["residual_z_down"]:
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
    elif weight_jumped:
        add("weight_change", f"직전 대회보다 계체 체중 {jump:+.1f}kg — 체중이 바뀐 대회는 기록 변화를 따로 판단하지 않아요")
    elif abs(bw_change) >= t["body_weight_change_pct"]:
        add("weight_change", f"최근 12개월 체중 {bw_change:+.1f}% (기준 ±{t['body_weight_change_pct']:.0f}%)")

    high_level_n = sum(r.competition_category in t["high_level_categories"] for r in records
                       if months_ago(r) <= t["high_level_window_months"])
    if high_level_n:
        add("high_level", f"최근 {t['high_level_window_months']}개월 안에 세계대회 또는 대륙대회 출전")

    if not tags:
        add("baseline", f"최근 기록이 예측 범위 안 ({z:+.1f}σ, 기준 ±{t['residual_z_up']:.1f}σ)" if z is not None
            else "경기력 예측 없이 기본 교육을 추천해요")

    recommendations: list[str] = []
    for tag in tags:
        contents = list(rules["tags"][tag]["contents"])
        first = rules["tags"][tag].get("emphasis_first")
        if first and emphasis_first:
            contents.remove(first)
            contents.insert(0, first)
        recommendations += [c for c in contents if c not in recommendations]

    # 판정 점검표: 붙지 않은 태그까지 규칙 입력값과 기준을 그대로 보여준다(D6 확장, 화면은 DEMO_MODE에서만).
    k = t["weight_jump_kg"]

    def performance_detail(threshold: float) -> str:
        if z is None:
            return "이 성별은 예측 모델이 없어 판단하지 않음"
        if weight_jumped:
            return f"체중이 바뀐 대회라 판단하지 않음 (직전 대비 계체 {jump:+.1f}kg, 기준 ±{k:.0f}kg 초과)"
        return f"예측 대비 {z:+.1f}σ (기준 {threshold:+.1f}σ)"

    weight_detail = next((r.text for r in reasons if r.tag == "weight_change"), None) or (
        f"체급 변경 없음 · 직전 대비 계체 {jump:+.1f}kg (기준 ±{k:.0f}kg 초과) · "
        + (f"최근 12개월 체중 {bw_change:+.1f}% (기준 ±{t['body_weight_change_pct']:.0f}%)" if year_ago
           else "12개월 전 기록 없음"))
    checks = [RuleCheck(tag=tag, label=tag_label(tag), met=tag in tags, detail=detail) for tag, detail in [
        ("rapid_improvement", performance_detail(t["residual_z_up"])),
        ("decline", performance_detail(t["residual_z_down"])),
        ("weight_change", weight_detail),
        ("high_level", f"마지막 대회 기준 {t['high_level_window_months']}개월 안의 세계·대륙대회 {high_level_n}회 "
                       f"(기준 1회 이상)"),
    ]]

    forecast = []
    if model != "none":
        for i in range(p["min_history"], len(records)):
            f = predict(sex, records, record_ages, i, p)
            forecast.append(ForecastPoint(date=records[i].date, mean=round(f.mean, 1), lo=round(f.lo, 1),
                                          hi=round(f.hi, 1)))
    return Result(model, tags, reasons, recommendations, forecast, notices, checks)


def to_records(req: ComputeRequest) -> list[Record]:
    return [Record(r.date, r.competition_category, weight_class(req.sex, r.body_weight), r.body_weight, r.snatch,
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
    """입력 → API 형태 프로파일 + 세션에 넣을 최소 정보(D15: 태그·연령대·대회 범주만). 저장하지 않는다."""
    records = to_records(req)
    result = evaluate(req.sex, req.birth_year, records)
    last = records[-1]
    age = int(last.date[:4]) - req.birth_year
    profile = AthleteProfile(
        athlete_id="self",
        sport="weightlifting",
        sex=req.sex,
        age=age,
        weight_class=last.weight_class,
        competition_category=last.competition_category,
        model=result.model,
        notices=result.notices,
        records=[RecordPoint(date=r.date, competition_category=r.competition_category, weight_class=r.weight_class,
                             body_weight=r.body_weight, snatch=r.snatch, clean_jerk=r.clean_jerk, total=r.total)
                 for r in records],
        forecast=result.forecast,
        tags=result.tags,
        tag_labels=[tag_label(t) for t in result.tags],
        reasons=result.reasons,
        checks=result.checks,
        recommendations=[recommendation(c) for c in result.recommendations],
    )
    return profile, PromptProfile(tags=result.tags, age_band=age_band(age), competition_category=last.competition_category)
