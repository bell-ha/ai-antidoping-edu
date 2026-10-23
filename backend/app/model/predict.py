"""경기력 예측 계산. 대회 기록 → 마지막 대회 합계 예측.

모델 파일은 MODEL_DIR(기본 backend/settings/)의 model_params.json이 정한다.
  synthetic_trend : 공개용 합성 추세 모델(누구나 실행해 볼 수 있게). 성별 연령 곡선 + 개인 오프셋.
  rnn             : 연구진 RNN(LSTM) 가중치를 numpy로 추론(app.model.rnn_infer). 성별마다 파일이 따로 있고,
                    없는 성별은 예측하지 않는다(model "none").
플랫폼은 모델을 학습하지 않고 결과만 쓴다. 서버에 torch는 없다.
"""

import json
from dataclasses import dataclass
from functools import cache

from app.config import MODEL_DIR

TOP_CLASS = 999  # 최상위 무제한 체급(+109 / +87)
# 입력 범주 → 연구진 모델의 event_category 토큰. 국내 대회는 학습 자료에 없어 "etc"로 보낸다.
EVENT_TOKEN = {"world": "world", "continent": "continent", "other_international": "nation", "domestic": "etc"}


@cache
def params() -> dict:
    return json.loads((MODEL_DIR / "model_params.json").read_text(encoding="utf-8"))


def params_source() -> str:
    """"synthetic"이면 시범 모드(DEMO_MODE=0)에서 서버가 시작을 거부한다(main.pilot_problems)."""
    return params()["source"]


def weight_class(sex: str, body_weight: float, classes: dict | None = None) -> int:
    """2018 IWF 체급. 계체 체중 이하인 가장 가벼운 체급 상한, 넘으면 최상위 체급."""
    limits = (classes or params()["classes"])[sex]
    return next((c for c in limits if c != TOP_CLASS and body_weight <= c), TOP_CLASS)


@dataclass(frozen=True)
class Record:
    date: str  # "YYYY-MM"
    competition_category: str
    weight_class: int
    body_weight: float
    snatch: int
    clean_jerk: int

    @property
    def total(self) -> int:
        return self.snatch + self.clean_jerk


def to_records(sex: str, rows: list) -> list[Record]:
    """date·competition_category·body_weight·snatch·clean_jerk가 있는 행들 → 계산용 기록(체급은 여기서 도출)."""
    return [Record(r.date, r.competition_category, weight_class(sex, r.body_weight), r.body_weight, r.snatch, r.clean_jerk)
            for r in rows]


def ages(birth_year: int, records: list[Record]) -> list[int]:
    """연구진 모델과 같은 정의: 대회연도 − 출생연도."""
    return [int(r.date[:4]) - birth_year for r in records]


# ---------- synthetic_trend ----------

def _ratio(sex: str, age: float, p: dict) -> float:
    a, b, c = p["curves"][sex]
    return a * age * age + b * age + c


def mean_prediction(sex: str, records: list[Record], record_ages: list[int], upto: int, p: dict | None = None) -> float:
    """records[:upto]만 보고 records[upto]의 합계를 예측."""
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
    from app.model import rnn_infer  # numpy는 rnn 경로에서만 필요하다
    meta = json.loads((MODEL_DIR / f"{name}.json").read_text(encoding="utf-8"))
    return meta, rnn_infer.load(MODEL_DIR / f"{name}.npz")


def rnn_mean(name: str, records: list[Record], record_ages: list[int], upto: int) -> float:
    from app.model import rnn_infer
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
