"""오프라인 분석 진입점 (D2): 합성 데이터 → 예측 → 교육 프로파일 → data/profiles.json, data/team_summary.json

    cd analysis && python export.py            # 데모 (팀 요약 k=1)
    cd analysis && python export.py --min-k 3 --out /srv/adedu/data  # Phase 2 (§10)

Phase 2에서 실제 선수로 만든 profiles.json은 레포와 컨테이너 이미지에 넣지 않는다. --out으로 서버의 별도
경로에 쓰고, 컨테이너에는 읽기 전용 볼륨으로 붙인다(공개 대회 기록이라 가명이어도 재식별 가능, §10 P-7).

페르소나마다 의도한 태그 하나만 붙었는지 검사하고, 아니면 아무것도 쓰지 않고 실패한다.
"""

import argparse
import json
from pathlib import Path

import yaml

from make_synthetic import Athlete, generate
from predict import MIN_HISTORY, TrendModel
from education_profile import age_band, build

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TAGS = {"A": ["rapid_improvement"], "B": ["decline"], "C": ["weight_change"],
                 "D": ["high_level"], "E": ["baseline"]}
# 지도자 데모 팀. 페르소나 전원을 넣으면 팀 요약이 카탈로그 전체와 같아져 집계가 보이지 않는다(S4).
DEMO_TEAM = ("demo-team", ["A", "C", "E"])


def forecast(a: Athlete, model: TrendModel) -> list[dict]:
    """각 대회를 직전 기록만으로 예측한 값(한 걸음 앞 예측). 차트의 예측 밴드."""
    out = []
    for i in range(MIN_HISTORY, len(a.records)):
        p = model.predict(a, i)
        out.append({"date": a.records[i].date, "mean": round(p.mean, 1), "lo": round(p.lo, 1), "hi": round(p.hi, 1)})
    return out


def record_json(a: Athlete, model: TrendModel, rules: dict, peers: list[Athlete]) -> dict:
    profile = build(a, model, rules, peers)
    last = a.records[-1]
    age = a.age_at(last.year)
    return {
        "athlete_id": a.athlete_id,
        "sport": "weightlifting",
        "sex": a.sex,
        "age": age,
        "age_band": age_band(age),
        "weight_class": last.weight_class,
        "competition_level": last.competition_level,
        "records": [{"date": r.date, "competition_level": r.competition_level, "weight_class": r.weight_class,
                     "body_weight": r.body_weight, "snatch": r.snatch, "clean_jerk": r.clean_jerk,
                     "total": r.total} for r in a.records],
        "forecast": forecast(a, model),
        "tags": profile.tags,
        "reasons": profile.reasons,
        "recommendations": profile.recommendations,
    }


def team_summary(team_id: str, profiles: list[dict], catalog_order: list[str], min_k: int) -> dict:
    """주제 목록만, 카탈로그 고정 순서, 인원수 없음 (D9). min_k 미만인 주제는 빼고 기본 교육으로 채운다."""
    counts = {c: sum(c in p["recommendations"] for p in profiles) for c in catalog_order}
    topics = [c for c in catalog_order if counts[c] >= min_k]
    return {"team_id": team_id, "topics": topics or ["anti-doping-basics"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-k", type=int, default=1)
    parser.add_argument("--out", type=Path, default=ROOT / "data", help="profiles.json·team_summary.json을 쓸 디렉터리")
    args = parser.parse_args()

    rules = yaml.safe_load((ROOT / "knowledge/rules.yaml").read_text(encoding="utf-8"))
    catalog = yaml.safe_load((ROOT / "knowledge/catalog.yaml").read_text(encoding="utf-8"))
    background, personas = generate()
    model = TrendModel.fit(background)

    profiles = [record_json(a, model, rules, background) for a in personas]
    wrong = {p["athlete_id"]: p["tags"] for p in profiles if p["tags"] != EXPECTED_TAGS[p["athlete_id"]]}
    if wrong:
        raise SystemExit(f"페르소나 태그가 설계(§2)와 다름: {wrong}")
    unknown = {c for p in profiles for c in p["recommendations"]} - set(catalog["contents"])
    if unknown:
        raise SystemExit(f"catalog.yaml에 없는 content_id: {sorted(unknown)}")

    team_id, members = DEMO_TEAM
    teams = [team_summary(team_id, [p for p in profiles if p["athlete_id"] in members], list(catalog["contents"]), args.min_k)]
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "profiles.json").write_text(json.dumps(profiles, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "team_summary.json").write_text(json.dumps(teams, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for p in profiles:
        print(p["athlete_id"], p["tags"], "|", " / ".join(r["text"] for r in p["reasons"]))
    print("배경 선수", len(background), "명, 체급별 σ(kg):",
          {f"{s}{c}": round(v, 1) for (s, c), v in sorted(model.sigma.items())})


if __name__ == "__main__":
    main()
