from datetime import date

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app import config, profiling, rag, substances
from app.api import routes, session

def pilot_problems(today: date, secret: str) -> list[str]:
    """시범 모드(DEMO_MODE=0) 시작 관문 (§10 G1·G2·G3, D26). 하나라도 있으면 서버가 뜨지 않는다."""
    problems = []
    if secret == config.DEV_SECRET or len(secret) < 32:
        problems.append("SESSION_SECRET을 32자 이상 무작위 값으로 설정해야 합니다.")
    if pending := substances.unreviewed() + rag.unreviewed():
        problems.append(f"연구진 검토 전 항목 {len(pending)}개 (reviewed: false): {pending[:5]} …")
    if profiling.params_source() != "real":
        problems.append("예측 파라미터가 합성 데이터 기준입니다. 실제 경기 기록으로 다시 학습한 model_params.json을 넣으세요(D26).")
    if today > (expires := substances.list_expires()):
        problems.append(f"금지목록 유효기간이 {expires}에 끝났습니다. 새 금지목록으로 조회표와 코퍼스를 갱신하세요.")
    return problems


if not config.DEMO_MODE and (problems := pilot_problems(date.today(), config.SESSION_SECRET)):
    raise RuntimeError("시범 모드 시작 불가:\n- " + "\n- ".join(problems))

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
