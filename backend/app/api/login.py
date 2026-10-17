"""로그인 (D37). 가입 없음 — 관리자가 선수를 등록하면 로그인 코드가 나오고, 선수는 그 코드로 들어온다.

세션에는 역할과 id만 둔다. 요청마다 DB에서 다시 확인하므로 코드를 새로 발급하거나 선수를 끄면 기존 세션도 끊긴다.
"""

import csv
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request

from app import config, db
from app.schemas import DemoCode, LoginRequest, SessionInfo

router = APIRouter(prefix="/api")

MAX_FAILURES = 10  # IP당, WINDOW초 안에
WINDOW = 600
_failures: dict[str, list[float]] = defaultdict(list)


def _by_code(code: str) -> tuple[SessionInfo, str] | None:
    h = db.code_hash(code)
    with db.connect() as con:
        if row := con.execute("SELECT id, name FROM admins WHERE code_hash = ?", (h,)).fetchone():
            return SessionInfo(role="admin", label=row["name"]), h
        if row := con.execute("SELECT id, name FROM athletes WHERE code_hash = ? AND active = 1", (h,)).fetchone():
            return SessionInfo(role="athlete", athlete_id=row["id"], label=row["name"]), h
    return None


def current(request: Request) -> SessionInfo:
    found = _by_code_hash(request.session.get("code_hash", ""))
    if found is None:
        request.session.clear()
        raise HTTPException(401, "로그인 코드를 입력하세요.")
    return found


def _by_code_hash(h: str) -> SessionInfo | None:
    if not h:
        return None
    with db.connect() as con:
        if row := con.execute("SELECT id, name FROM admins WHERE code_hash = ?", (h,)).fetchone():
            return SessionInfo(role="admin", label=row["name"])
        if row := con.execute("SELECT id, name FROM athletes WHERE code_hash = ? AND active = 1", (h,)).fetchone():
            return SessionInfo(role="athlete", athlete_id=row["id"], label=row["name"])
    return None


def athlete(who: SessionInfo = Depends(current)) -> SessionInfo:
    if who.role != "athlete":
        raise HTTPException(403, "선수 계정으로 들어와야 해요.")
    return who


def admin(who: SessionInfo = Depends(current)) -> SessionInfo:
    if who.role != "admin":
        raise HTTPException(403, "관리자만 볼 수 있어요.")
    return who


def admin_id(request: Request) -> int | None:
    with db.connect() as con:
        row = con.execute("SELECT id FROM admins WHERE code_hash = ?", (request.session.get("code_hash", ""),)).fetchone()
    return row["id"] if row else None


def _throttle(ip: str) -> None:
    now = time.monotonic()
    recent = [t for t in _failures[ip] if now - t < WINDOW]
    _failures[ip] = recent
    if len(recent) >= MAX_FAILURES:
        raise HTTPException(429, "잠시 후 다시 시도하세요.")


@router.post("/session", response_model=SessionInfo)
def login(body: LoginRequest, request: Request) -> SessionInfo:
    ip = request.client.host if request.client else "unknown"
    _throttle(ip)
    found = _by_code(body.code)
    if found is None:
        _failures[ip].append(time.monotonic())
        raise HTTPException(401, "코드를 확인하세요.")
    request.session.clear()
    request.session["code_hash"] = found[1]
    return found[0]


@router.get("/session", response_model=SessionInfo)
def whoami(who: SessionInfo = Depends(current)) -> SessionInfo:
    return who


@router.delete("/session", status_code=204)
def logout(request: Request) -> None:
    request.session.clear()


@router.get("/demo/codes", response_model=list[DemoCode])
def demo_codes() -> list[DemoCode]:
    """데모에서 로그인을 쉽게: scripts/seed_dummy.py가 남긴 var/dummy_codes.csv. 시범(DEMO_MODE=0)에서는 없다."""
    path = config.APP_DB.parent / "dummy_codes.csv"
    if not config.DEMO_MODE or not path.exists():
        raise HTTPException(404)
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    with db.connect() as con:
        tier = {r["number"]: r["tier"] for r in con.execute("""SELECT a.number, t.tier FROM athletes a JOIN tier_assignments t
            ON t.athlete_id = a.id AND t.batch = (SELECT MAX(batch) FROM tier_assignments)""")}
    return [DemoCode(number=r["number"], name=r["name"], role=r["role"], code=r["code"], tier=tier.get(r["number"])) for r in rows]
