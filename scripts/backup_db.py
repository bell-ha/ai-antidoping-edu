"""운영 DB 백업. 서버가 켜져 있어도 된다(SQLite backup API).

    cd backend && .venv/bin/python ../scripts/backup_db.py
    docker compose exec app python /app/scripts/backup_db.py

- 결과: 운영 DB 옆 backups/app-<날짜시각>.sqlite (로컬은 var/backups/, Git 제외).
"""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import config  # noqa: E402


def main() -> None:
    if not config.APP_DB.exists():
        sys.exit(f"운영 DB가 없어요: {config.APP_DB}")
    out = config.APP_DB.parent / "backups" / f"app-{datetime.now():%Y%m%d-%H%M%S}.sqlite"
    out.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(config.APP_DB) as src, sqlite3.connect(out) as dst:
        src.backup(dst)
    print(f"→ {out}")


if __name__ == "__main__":
    main()
