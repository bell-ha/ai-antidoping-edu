"""운영 DB(SQLite, var/app.sqlite). 표 정의는 schema.sql (D37).

약물 DB(drugs.drug_db)와 파일을 나눈다. 저쪽은 원자료에서 다시 만들 수 있는 생성물이고,
이쪽은 다시 만들 수 없는 운영 기록이다. 레포·이미지에 넣지 않는다(.gitignore·.dockerignore).
"""

import hashlib
import hmac
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app import config

KST = ZoneInfo("Asia/Seoul")  # "하루"·"한 주" 기준: 한국 시간
_SCHEMA = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")


def code_hash(code: str) -> str:
    """로그인 코드 → 해시. 코드 원문은 저장하지 않는다."""
    return hmac.new(config.SESSION_SECRET.encode(), code.strip().encode(), hashlib.sha256).hexdigest()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """with connect() as con: … — 블록이 끝나면 커밋(예외면 롤백)하고 닫는다."""
    config.APP_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.APP_DB, timeout=5)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(_SCHEMA)
    try:
        with con:
            yield con
    finally:
        con.close()


def now() -> datetime:
    return datetime.now(KST)


def now_iso() -> str:
    return now().isoformat(timespec="seconds")


def today() -> str:
    return now().date().isoformat()


def week_start(day: date | None = None) -> str:
    """그 주 월요일(KST)."""
    d = day or now().date()
    return (d - timedelta(days=d.weekday())).isoformat()
