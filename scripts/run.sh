#!/usr/bin/env bash
# 서버 하나를 띄운다: http://127.0.0.1:8100 (화면 + API). Ctrl+C로 종료.
#   - private/models(연구진 모델, 비공개)가 있으면 그 모델, 없으면 공개용 합성 모델(backend/settings)을 쓴다.
#   - 처음이면 더미 선수 100명을 넣는다(var/app.sqlite에 선수가 없을 때만). 로그인 코드는 var/dummy_codes.csv.
#   - .env(레포 루트, Git 제외)가 있으면 읽는다: ANTHROPIC_API_KEY=…, LLM_MODE=live, (조직 키면) ANTHROPIC_WORKSPACE_ID=…
# 8000번은 다른 프로젝트가 쓰므로 피한다.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .env ]; then set -a; . ./.env; set +a; fi

(cd frontend && npm run build >/dev/null)
PY="$PWD/backend/.venv/bin/python"
export DEMO_MODE="${DEMO_MODE:-1}" LLM_MODE="${LLM_MODE:-mock}"

(cd backend && "$PY" ../scripts/seed_dummy.py 2>/dev/null) || true
echo "http://127.0.0.1:${PORT:-8100}"
cd backend && exec "$PY" -m uvicorn app.main:app --port "${PORT:-8100}"
