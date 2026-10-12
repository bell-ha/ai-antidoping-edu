"""오프라인 분석 진입점 (D2, D25).

    cd analysis && ../backend/.venv/bin/python export.py

합성 데이터 → 모집단 파라미터 학습 → data/model_params.json
페르소나 A~E + 테스트 시나리오(analysis/scenarios.py) → data/demo_examples.json
  (화면의 "입력 예시 채우기"·"테스트 시나리오", 선수 직접 입력과 같은 경로를 탄다)

모든 예시의 태그와 입력 경고를 서버와 같은 함수(app.profiling)로 계산해 손으로 적은 기대값(합성 모델)과
비교하고, 다르면 실패한다. 실모델(rnn) 기대값은 private/models가 있을 때 레포 테스트가 확인한다. 추론·규칙 코드는 backend/app/profiling.py 하나뿐이다.

실제 경기 기록으로 파라미터를 다시 학습할 때는 make_synthetic 대신 실제 데이터를 넣고
`--source real --out <서버의 별도 경로>`로 내보낸다. 실제 데이터와 그 산출물은 레포와 컨테이너 이미지에
넣지 않는다(§10).
"""

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import profiling  # noqa: E402
from app.schemas import ComputeRequest  # noqa: E402
from make_synthetic import Athlete, generate  # noqa: E402
from predict import CATEGORY, fit  # noqa: E402
from scenarios import build  # noqa: E402

EXAMPLE_ROWS = 8  # C의 체급 변경(약 15개월 전)이 18개월 창 안팎으로 함께 보이려면 6행 이상 필요


def example(a: Athlete) -> dict:
    rows = a.records[-EXAMPLE_ROWS:]
    return {"sex": a.sex, "birth_year": a.birth_year,
            "records": [{"date": r.date, "competition_category": CATEGORY[r.competition_level],
                         "body_weight": r.body_weight, "snatch": r.snatch, "clean_jerk": r.clean_jerk} for r in rows]}


def write(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["synthetic", "real"], default="synthetic")
    parser.add_argument("--out", type=Path, default=ROOT / "data", help="산출물 디렉터리")
    args = parser.parse_args()

    background, personas = generate()
    params = fit(background, args.source)
    examples = {a.athlete_id: example(a) for a in personas}

    # 서버와 같은 경로로 계산해 검사한다. profiling.params()는 MODEL_DIR/model_params.json을 읽으므로 먼저 써 둔다.
    args.out.mkdir(parents=True, exist_ok=True)
    write(args.out / "model_params.json", params)
    profiling.MODEL_DIR = args.out
    profiling.params.cache_clear()
    examples = build(examples)
    requests = {aid: ComputeRequest(**ex) for aid, ex in examples.items()}
    results = {aid: profiling.compute(req)[0] for aid, req in requests.items()}

    wrong = {aid: (p.tags, examples[aid]["expect"]["synthetic_trend"]) for aid, p in results.items()
             if p.tags != examples[aid]["expect"]["synthetic_trend"]}
    for aid, req in requests.items():
        codes = [w.code for w in profiling.validate(req)]
        if codes != examples[aid]["warnings"]:
            wrong[aid] = (codes, examples[aid]["warnings"])
    if wrong:
        raise SystemExit(f"기대값과 다름 (계산, 기대): {wrong}")

    write(args.out / "demo_examples.json", examples)

    for aid, p in results.items():
        print(aid, examples[aid]["label"], p.tags, "|", " / ".join(r.text for r in p.reasons))
    print("배경 선수", len(background), "명, source =", params["source"])


if __name__ == "__main__":
    main()
