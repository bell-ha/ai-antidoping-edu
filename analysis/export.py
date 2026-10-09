"""오프라인 분석 진입점 (D2, D25).

    cd analysis && ../backend/.venv/bin/python export.py

합성 데이터 → 모집단 파라미터 학습 → data/model_params.json
페르소나 A~E → data/demo_examples.json (화면의 "입력 예시 채우기", 선수 직접 입력과 같은 경로를 탄다)
데모 팀(A·C·E) → data/team_summary.json (지도자 화면, DEMO_MODE에서만)

페르소나의 태그는 서버와 같은 함수(app.profiling.compute)로 계산해 검사한다. 의도한 태그(§2)와 다르면
실패한다. 추론·규칙 코드는 backend/app/profiling.py 하나뿐이다.

실제 경기 기록으로 파라미터를 다시 학습할 때는 make_synthetic 대신 실제 데이터를 넣고
`--source real --out <서버의 별도 경로>`로 내보낸다. 실제 데이터와 그 산출물은 레포와 컨테이너 이미지에
넣지 않는다(§10).
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import profiling  # noqa: E402
from app.schemas import ComputeRequest  # noqa: E402
from make_synthetic import Athlete, generate  # noqa: E402
from predict import fit  # noqa: E402

EXPECTED_TAGS = {"A": ["rapid_improvement"], "B": ["decline"], "C": ["weight_change"],
                 "D": ["high_level"], "E": ["baseline"]}
EXAMPLE_ROWS = 8  # C의 체급 변경(약 15개월 전)이 18개월 창 안팎으로 함께 보이려면 6행 이상 필요
# 지도자 데모 팀. 페르소나 전원을 넣으면 팀 요약이 카탈로그 전체와 같아져 집계가 보이지 않는다(S4).
DEMO_TEAM = ("demo-team", ["A", "C", "E"])


def example(a: Athlete) -> dict:
    rows = a.records[-EXAMPLE_ROWS:]
    return {"sex": a.sex, "age": a.age_at(rows[-1].year),
            "records": [{"date": r.date, "competition_level": r.competition_level, "body_weight": r.body_weight,
                         "snatch": r.snatch, "clean_jerk": r.clean_jerk} for r in rows]}


def team_summary(team_id: str, recommendations: list[list[str]], catalog_order: list[str], min_k: int) -> dict:
    """주제 목록만, 카탈로그 고정 순서, 인원수 없음 (D9). min_k 미만인 주제는 빼고 기본 교육으로 채운다."""
    counts = {c: sum(c in recs for recs in recommendations) for c in catalog_order}
    topics = [c for c in catalog_order if counts[c] >= min_k]
    return {"team_id": team_id, "topics": topics or ["anti-doping-basics"]}


def write(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-k", type=int, default=1, help="팀 요약: 주제당 최소 선수 수 (Phase 2는 3)")
    parser.add_argument("--source", choices=["synthetic", "real"], default="synthetic")
    parser.add_argument("--out", type=Path, default=ROOT / "data", help="산출물 디렉터리")
    args = parser.parse_args()

    background, personas = generate()
    params = fit(background, args.source)
    examples = {a.athlete_id: example(a) for a in personas}

    # 서버와 같은 경로로 계산해 검사한다. profiling.params()는 DATA/model_params.json을 읽으므로 먼저 써 둔다.
    args.out.mkdir(parents=True, exist_ok=True)
    write(args.out / "model_params.json", params)
    profiling.DATA = args.out
    profiling.params.cache_clear()
    results = {aid: profiling.compute(ComputeRequest(**ex))[0] for aid, ex in examples.items()}

    wrong = {aid: p.tags for aid, p in results.items() if p.tags != EXPECTED_TAGS[aid]}
    if wrong:
        raise SystemExit(f"페르소나 태그가 설계(§2)와 다름: {wrong}")

    catalog = yaml.safe_load((ROOT / "knowledge/catalog.yaml").read_text(encoding="utf-8"))
    team_id, members = DEMO_TEAM
    team = team_summary(team_id, [[r.content_id for r in results[m].recommendations] for m in members],
                        list(catalog["contents"]), args.min_k)
    write(args.out / "demo_examples.json", examples)
    write(args.out / "team_summary.json", [team])

    for aid, p in results.items():
        print(aid, p.tags, "|", " / ".join(r.text for r in p.reasons))
    print("배경 선수", len(background), "명, source =", params["source"])


if __name__ == "__main__":
    main()
