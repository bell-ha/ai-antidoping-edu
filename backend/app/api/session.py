"""접근 코드 세션 (D23). role·athlete_id·team_id는 여기서만 나온다."""

import json
import time
from collections import defaultdict
from functools import cache

from fastapi import APIRouter, Depends, HTTPException, Request

from app import config
from app.schemas import DemoPersona, SessionInfo, SessionRequest

router = APIRouter(prefix="/api")

MAX_FAILURES = 10  # IP당, WINDOW초 안에
WINDOW = 600
_failures: dict[str, list[float]] = defaultdict(list)


@cache
def _demo() -> dict[str, dict]:
    path = config.DATA / "demo_codes.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


@cache
def _access() -> dict[str, SessionInfo]:
    path = config.DATA / "access_codes.json"
    if not path.exists():
        return {}
    return {code: SessionInfo.model_validate(v) for code, v in json.loads(path.read_text(encoding="utf-8")).items()}


def lookup(code: str) -> SessionInfo | None:
    if config.DEMO_MODE and code in _demo():
        return SessionInfo.model_validate(_demo()[code]["info"])
    return _access().get(code)


def current(request: Request) -> SessionInfo:
    """매 요청마다 코드를 다시 조회한다. 코드를 폐기하면 기존 세션도 바로 끊긴다."""
    info = lookup(request.session.get("code", ""))
    if info is None:
        request.session.clear()
        raise HTTPException(401, "접근 코드를 입력하세요.")
    return info


def _throttle(ip: str) -> None:
    now = time.monotonic()
    recent = [t for t in _failures[ip] if now - t < WINDOW]
    _failures[ip] = recent
    if len(recent) >= MAX_FAILURES:
        raise HTTPException(429, "잠시 후 다시 시도하세요.")


@router.post("/session", response_model=SessionInfo)
def login(body: SessionRequest, request: Request) -> SessionInfo:
    ip = request.client.host if request.client else "unknown"
    _throttle(ip)
    info = lookup(body.code.strip())
    if info is None:
        _failures[ip].append(time.monotonic())
        raise HTTPException(401, "코드를 확인하세요.")
    request.session["code"] = body.code.strip()
    return info


@router.get("/session", response_model=SessionInfo)
def whoami(who: SessionInfo = Depends(current)) -> SessionInfo:
    return who


@router.delete("/session", status_code=204)
def logout(request: Request) -> None:
    request.session.clear()


@router.get("/demo/personas", response_model=list[DemoPersona])
def personas() -> list[DemoPersona]:
    if not config.DEMO_MODE:
        raise HTTPException(404)
    return [DemoPersona(code=code, info=v["info"], description=v["description"]) for code, v in _demo().items()]
