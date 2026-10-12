"""환경변수 설정. 기본값은 키 없이 로컬에서 도는 개발 모드."""

import os
from pathlib import Path
from typing import Literal, cast

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
# 예측 모델 파일(model_params.json, rnn_*.npz/json)만 다른 곳에서 읽을 때. 실데이터 산출물은 레포 밖에 둔다(D26)
MODEL_DIR = Path(os.environ.get("MODEL_DIR", DATA))

LlmMode = Literal["mock", "live", "record", "replay"]

LLM_MODE = cast(LlmMode, os.environ.get("LLM_MODE", "mock"))  # D16
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")  # D15
DEMO_MODE = os.environ.get("DEMO_MODE", "1") == "1"  # D23: 데모 코드는 이때만 유효
DEV_SECRET = "dev-only-secret-change-me"
SESSION_SECRET = os.environ.get("SESSION_SECRET", DEV_SECRET)
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"  # 로컬 개발만 0
LLM_CACHE_DIR = DATA / "llm_cache"
