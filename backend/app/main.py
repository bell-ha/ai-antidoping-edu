"""서버 하나: API + 화면(frontend/dist). 실행: cd backend && .venv/bin/python -m uvicorn app.main:app --port 8100"""

import sys
from datetime import date

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app import config
from app.api import admin, athlete, chat, library, login
from app.chat import retrieve
from app.drugs import substances
from app.model import predict


def pilot_problems(secret: str) -> list[str]:
    """시범 모드(DEMO_MODE=0)에서 서버를 막는 것은 비밀키 하나. 저장소가 공개라 기본 비밀키로는 누구나 로그인 쿠키를 만들 수 있다."""
    if secret == config.DEV_SECRET or len(secret) < 32:
        return ["SESSION_SECRET을 32자 이상 무작위 값으로 설정해야 합니다."]
    return []


def pilot_notes(today: date) -> list[str]:
    """시범 모드에서 알려만 주는 것(서버는 뜬다). 사람 검토·실제 모델·유효기간으로는 막지 않기로 함(사용자, 2026-10-23)."""
    notes = []
    if pending := substances.unreviewed() + retrieve.unreviewed():
        notes.append(f"사람 검토 전 항목 {len(pending)}개 (reviewed: false)")
    if predict.params_source() != "real":
        notes.append("예측 모델이 합성 데이터 기준입니다. 연구진 모델은 private/models에 넣으세요.")
    if today > (expires := substances.list_expires()):
        notes.append(f"금지목록 유효기간이 {expires}에 끝났습니다. 새 금지목록으로 조회표를 갱신하세요.")
    return notes


if not config.DEMO_MODE:
    if problems := pilot_problems(config.SESSION_SECRET):
        raise RuntimeError("시범 모드 시작 불가:\n- " + "\n- ".join(problems))
    for note in pilot_notes(date.today()):
        print(f"시범 모드 알림: {note}", file=sys.stderr)

app = FastAPI(title="AI 반도핑 교육")
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET,
    session_cookie="adedu_session",
    same_site="lax",
    https_only=config.COOKIE_SECURE,
    max_age=60 * 60 * 12,
)


@app.get("/api/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}


for r in (login.router, athlete.router, admin.router, chat.router, library.router):
    app.include_router(r)

dist = config.ROOT / "frontend" / "dist"
if dist.exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        """/admin 같은 화면 주소로 바로 들어와도 index.html을 준다. /api/는 여기 오지 않는다."""
        if path.startswith("api/"):
            raise HTTPException(404)
        file = (dist / path).resolve()
        if path and file.is_file() and file.is_relative_to(dist.resolve()):
            return FileResponse(file)
        return FileResponse(dist / "index.html")
