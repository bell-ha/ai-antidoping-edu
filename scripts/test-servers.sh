#!/usr/bin/env bash
# 테스트용 서버 두 개를 띄운다 (docs/TESTING.md).
#   :8101  합성 추세 모델(data/model_params.json) — 누구나 재현 가능
#   :8102  연구진 RNN 실모델(MODEL_DIR=private/models) — private/models가 있을 때만
# 둘 다 DEMO_MODE=1, LLM_MODE=mock. 8000번은 다른 프로젝트가 쓰므로 피한다. Ctrl+C로 함께 종료.
set -euo pipefail
cd "$(dirname "$0")/.."

(cd frontend && npm run build >/dev/null)
PY=backend/.venv/bin/python
export DEMO_MODE=1 LLM_MODE="${LLM_MODE:-mock}"

pids=()
trap 'kill "${pids[@]}" 2>/dev/null' EXIT INT TERM

(cd backend && exec ../$PY -m uvicorn app.main:app --port 8101) &
pids+=($!)
echo "합성 모델:  http://127.0.0.1:8101"

if [ -f private/models/model_params.json ]; then
  (cd backend && MODEL_DIR="$PWD/../private/models" exec ../$PY -m uvicorn app.main:app --port 8102) &
  pids+=($!)
  echo "연구진 RNN: http://127.0.0.1:8102"
else
  echo "private/models가 없어 RNN 서버(:8102)는 건너뜀"
fi
wait
