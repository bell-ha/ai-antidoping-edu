"""관리자 '교육 자료' 화면에서 사람이 남긴 검토 표시를 레슨 파일에 반영한다(사람이 직접 실행).

    cd backend && .venv/bin/python ../scripts/apply_reviews.py          # 미리 보기(파일은 그대로)
    cd backend && .venv/bin/python ../scripts/apply_reviews.py --write  # '검토 완료' 레슨의 reviewed: true로 저장

- '검토 완료'만 반영하고, '고칠 곳 있음'은 메모와 함께 목록으로 보여 준다(고친 뒤 다시 검토).
- 반영한 뒤 git diff로 확인하고 커밋한다.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import config, db  # noqa: E402


def main() -> None:
    write = "--write" in sys.argv
    with db.connect() as con:
        rows = con.execute("SELECT lesson_id, status, note, at FROM lesson_reviews ORDER BY lesson_id").fetchall()
    files = {p.stem: p for p in config.LESSONS.rglob("*.md")}
    done = [r for r in rows if r["status"] == "reviewed" and r["lesson_id"] in files]
    fix = [r for r in rows if r["status"] == "needs_fix"]
    changed = 0
    for r in done:
        path = files[r["lesson_id"]]
        text = path.read_text(encoding="utf-8")
        new = re.sub(r"^reviewed: false$", "reviewed: true", text, count=1, flags=re.M)
        if new != text:
            changed += 1
            if write:
                path.write_text(new, encoding="utf-8")
    print(f"검토 완료 {len(done)}개 중 파일에 새로 반영할 것 {changed}개" + ("(저장함)" if write else "(미리 보기 — 저장하려면 --write)"))
    if fix:
        print(f"\n고칠 곳 있음 {len(fix)}개:")
        for r in fix:
            print(f"- {r['lesson_id']} ({r['at'][:10]}): {r['note'] or '(메모 없음)'}")


if __name__ == "__main__":
    main()
