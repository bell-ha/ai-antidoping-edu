from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app import config, rag, substances
from app.api import routes, session

# 시범 모드(DEMO_MODE=0) 시작 관문 (§10 G2)
if not config.DEMO_MODE:
    if config.SESSION_SECRET == config.DEV_SECRET or len(config.SESSION_SECRET) < 32:
        raise RuntimeError("DEMO_MODE=0에서는 SESSION_SECRET을 32자 이상 무작위 값으로 설정해야 합니다.")
    if pending := substances.unreviewed() + rag.unreviewed():
        raise RuntimeError(f"연구진 검토 전 항목 {len(pending)}개 (reviewed: false): {pending[:5]} …")

app = FastAPI(title="AI 반도핑 맞춤형 교육")
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
    """인증 없는 헬스체크. 상태 문자열만 돌려준다."""
    return {"status": "ok"}


app.include_router(session.router)
app.include_router(routes.router)

# 시연: 프론트 빌드를 같은 프로세스에서 서빙 (D18)
dist = config.ROOT / "frontend" / "dist"
if dist.exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        """/performance 같은 화면 주소로 바로 들어와도 index.html을 준다. /api/는 여기 오지 않는다."""
        if path.startswith("api/"):
            raise HTTPException(404)
        file = (dist / path).resolve()
        if path and file.is_file() and file.is_relative_to(dist.resolve()):
            return FileResponse(file)
        return FileResponse(dist / "index.html")
