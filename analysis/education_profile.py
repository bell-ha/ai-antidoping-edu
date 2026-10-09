"""교육 프로파일 (D5, D6, D8). 규칙 = knowledge/rules.yaml, 표의 행 순서대로 태그를 붙인다.

추천 이유(reasons)는 규칙 입력값을 그대로 보여준다(D6). 백분위는 high_level 추천 순서를
바꾸는 데만 쓰고 반환값에 넣지 않는다(D8).
"""

from dataclasses import dataclass

import numpy as np

from make_synthetic import TODAY, Athlete
from predict import TrendModel


@dataclass
class Profile:
    tags: list[str]
    reasons: list[dict]
    recommendations: list[str]


def months_ago(year: int, month: int) -> int:
    return (TODAY[0] - year) * 12 + TODAY[1] - month


def age_band(age: int) -> str:
    if age < 18:
        return "18세 미만"
    if age < 21:
        return "18-20세"
    if age < 25:
        return "21-24세"
    return f"{age // 5 * 5}-{age // 5 * 5 + 4}세"


def percentile_in_age_class(a: Athlete, peers: list[Athlete]) -> float:
    """동일 성별·체급·연령대 안에서 최근 합계의 백분위 (Ryoo & Suh 2022의 비교 단위)."""
    last = a.records[-1]
    band = age_band(a.age_at(last.year))
    totals = [p.records[-1].total for p in peers
              if p.sex == a.sex and p.records[-1].weight_class == last.weight_class
              and age_band(p.age_at(p.records[-1].year)) == band]
    if not totals:
        return 0.0
    return 100.0 * float(np.mean(np.array(totals) <= last.total))


def build(a: Athlete, model: TrendModel, rules: dict, peers: list[Athlete]) -> Profile:
    t = rules["thresholds"]
    last_i = len(a.records) - 1
    last = a.records[last_i]
    p = model.predict(a, last_i)
    z = (last.total - p.mean) / p.sigma

    tags, reasons = [], []

    def add(tag, text):
        tags.append(tag)
        reasons.append({"tag": tag, "text": text})

    if z >= t["residual_z_up"]:
        add("rapid_improvement", f"최근 기록이 예측보다 {z:+.1f}σ 높음 (기준 +{t['residual_z_up']:.1f}σ)")
    if z <= t["residual_z_down"]:
        add("decline", f"최근 기록이 예측보다 {z:+.1f}σ 낮음 (기준 {t['residual_z_down']:.1f}σ)")

    recent_classes = [r.weight_class for r in a.records if months_ago(r.year, r.month) <= t["weight_class_window_months"]]
    earlier = [r for r in a.records if months_ago(r.year, r.month) > t["weight_class_window_months"]]
    year_ago = [r for r in a.records if months_ago(r.year, r.month) >= 12]
    bw_change = (last.body_weight / year_ago[-1].body_weight - 1) * 100 if year_ago else 0.0
    class_changed = bool(earlier) and any(c != earlier[-1].weight_class for c in recent_classes)
    if class_changed or abs(bw_change) >= t["body_weight_change_pct"]:
        if class_changed:
            before = earlier[-1]
            add("weight_change", f"최근 {t['weight_class_window_months']}개월 안에 체급 {before.weight_class}→"
                                 f"{last.weight_class}kg (체중 {before.body_weight}→{last.body_weight}kg)")
        else:
            add("weight_change", f"최근 12개월 체중 {bw_change:+.1f}% (기준 ±{t['body_weight_change_pct']:.0f}%)")

    if any(r.competition_level == "international" for r in a.records
           if months_ago(r.year, r.month) <= t["high_level_window_months"]):
        add("high_level", f"최근 {t['high_level_window_months']}개월 안에 국제대회 출전")

    if not tags:
        add("baseline", f"최근 기록이 예측 범위 안 ({z:+.1f}σ, 기준 ±{t['residual_z_up']:.1f}σ)")

    recommendations = []
    for tag in tags:
        contents = list(rules["tags"][tag]["contents"])
        first = rules["tags"][tag].get("emphasis_first")
        lo, hi = t["emphasis_percentile"]
        if first and lo <= percentile_in_age_class(a, peers) <= hi:
            contents.remove(first)
            contents.insert(0, first)
        recommendations += [c for c in contents if c not in recommendations]

    return Profile(tags, reasons, recommendations)
