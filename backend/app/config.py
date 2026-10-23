"""환경변수 설정. 기본값은 키 없이 로컬에서 도는 개발 모드."""

import os
from pathlib import Path
from typing import Literal, cast

ROOT = Path(__file__).resolve().parents[2]
# 앱이 쓰는 원자료: knowledge/drugs(약물 정보)와 knowledge/education(교육)
KNOWLEDGE = ROOT / "knowledge"
EDUCATION = KNOWLEDGE / "education"  # 교육 레슨과 그 원자료 — 질문하기의 근거, 교육 자료 화면
DRUGS = KNOWLEDGE / "drugs"  # 약물 판정용 목록 — 판정 규칙이 씀(AI 아님)
LESSONS = EDUCATION / "lessons"  # 레슨 300개(텍스트 + 객관식 퀴즈 1문항)
# 앱 설정(knowledge가 아님): 단계 기본값(program.yaml), 검색 동의어(synonyms.yaml), 공개용 합성 모델
SETTINGS = ROOT / "backend" / "settings"
# 실행하면 생기는 것(Git 제외): 운영 DB, 약물 DB, 더미 로그인 코드
VAR = Path(os.environ.get("VAR_DIR", ROOT / "var"))
# 예측 모델 파일(model_params.json, rnn_*.npz/json). private/models(연구진 모델, 비공개)가 있으면 그것을,
# 없으면 공개용 합성 모델(backend/settings)을 쓴다 — 서버는 하나
_PRIVATE_MODELS = ROOT / "private" / "models"
MODEL_DIR = Path(os.environ.get("MODEL_DIR") or (_PRIVATE_MODELS if (_PRIVATE_MODELS / "model_params.json").exists() else SETTINGS))

LlmMode = Literal["mock", "live", "record", "replay"]

LLM_MODE = cast(LlmMode, os.environ.get("LLM_MODE", "mock"))  # mock(키 없이 고정 답) · live · record · replay
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
# 워크스페이스에 묶이지 않은 조직 키를 쓸 때만 필요(없으면 API가 400). 워크스페이스 키면 비워 둔다
ANTHROPIC_WORKSPACE_ID = os.environ.get("ANTHROPIC_WORKSPACE_ID", "")
DEMO_MODE = os.environ.get("DEMO_MODE", "1") == "1"  # 0이면 시범 모드 시작 관문(main.pilot_problems)을 건다
DEV_SECRET = "dev-only-secret-change-me"
SESSION_SECRET = os.environ.get("SESSION_SECRET", DEV_SECRET)
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"  # 로컬 개발만 0
LLM_CACHE_DIR = VAR / "llm_cache"  # LLM_MODE=record/replay용
# 운영 DB(선수·기록·단계·교육 이수·퀴즈·질문). 레포·이미지 밖 기록
APP_DB = Path(os.environ.get("APP_DB", VAR / "app.sqlite"))
DAILY_CHAT_LIMIT = int(os.environ.get("DAILY_CHAT_LIMIT", "30"))  # 사용자별 하루 AI 답변 생성 횟수(비용 한도)
# 외부 설문(사전·사후 평가) 주소. "{pid}" 자리에 선수 번호(WL-001 등)가 들어간다(api/athlete.py survey)
SURVEY_URL = os.environ.get("SURVEY_URL", "")
