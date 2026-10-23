"""관리자 만들기. 시범 운영(더미 없이)에서 첫 관리자 코드를 받는 방법.

    cd backend && .venv/bin/python ../scripts/create_admin.py 이름
    docker compose exec app python /app/scripts/create_admin.py 이름

- 로그인 코드는 화면에 한 번만 보여 준다(DB에는 해시만). 잃어버리면 새 관리자를 다시 만든다.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import db  # noqa: E402
from app.api.admin import new_code  # noqa: E402


def main() -> None:
    name = " ".join(sys.argv[1:]).strip()
    if not name:
        sys.exit("관리자 이름을 적어 주세요. 예: create_admin.py 홍길동")
    code = new_code("ADMIN")
    with db.connect() as con:
        con.execute("INSERT INTO admins (name, code_hash, created_at) VALUES (?, ?, ?)", (name, db.code_hash(code), db.now_iso()))
    print(f"관리자 {name} 로그인 코드: {code}  (다시 보여 주지 않아요)")


if __name__ == "__main__":
    main()
