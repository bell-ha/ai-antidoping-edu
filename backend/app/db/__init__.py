"""운영 DB(SQLite, var/app.sqlite). 표 정의는 schema.sql.

약물 DB(drugs.drug_db)와 파일을 나눈다. 저쪽은 원자료에서 다시 만들 수 있는 생성물이고,
이쪽은 다시 만들 수 없는 운영 기록이다. 레포·이미지에 넣지 않는다(.gitignore·.dockerignore).
"""

import hashlib
import hmac
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app import config

KST = ZoneInfo("Asia/Seoul")  # "하루"·"한 주" 기준: 한국 시간
_SCHEMA = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")


_CODE = re.compile(r"\b(ADMIN|[A-Z]{2,4}-\d{2,})-([A-Z0-9]{4,})\b", re.IGNORECASE)


def canonical_code(code: str) -> str:
    """로그인 코드 표기 맞추기(테스터 다수, 2026-11-17): 번호는 대문자, 끝 덩어리는 소문자로(휴대폰 자동 대문자 대비).
    안내문을 통째로 붙여 넣어도 코드만 뽑는다. 발급되는 코드는 이미 이 모양이라 기존 해시는 그대로 맞는다."""
    m = _CODE.search(code)
    return f"{m.group(1).upper()}-{m.group(2).lower()}" if m else code.strip()


def code_hash(code: str) -> str:
    """로그인 코드 → 해시. 코드 원문은 저장하지 않는다."""
    return hmac.new(config.SESSION_SECRET.encode(), canonical_code(code).encode(), hashlib.sha256).hexdigest()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """with connect() as con: … — 블록이 끝나면 커밋(예외면 롤백)하고 닫는다."""
    config.APP_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.APP_DB, timeout=5)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(_SCHEMA)
    _migrate(con)
    try:
        with con:
            yield con
    finally:
        con.close()


def _migrate(con: sqlite3.Connection) -> None:
    """이미 만들어진 DB에 새 칸 더하기(schema.sql은 CREATE IF NOT EXISTS라 칸 추가가 반영되지 않음).
    tier: 배정·풀이 당시의 단계(CSV에서 지금 단계로 덮어써지지 않게, 테스터 2)."""
    for table in ("lesson_assignments", "quiz_attempts"):
        if "tier" not in {r[1] for r in con.execute(f"PRAGMA table_info({table})")}:
            con.execute(f"ALTER TABLE {table} ADD COLUMN tier INTEGER")


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
