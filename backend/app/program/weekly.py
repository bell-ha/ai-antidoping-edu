"""매주 단계별 개수만큼 레슨 배정 (D37).

그 주에 처음 들어왔을 때 배정한다: 아직 배정된 적 없는 레슨을 커리큘럼 순서(A→M)대로 단계의 주당 개수만큼.
지난주에 못 들은 레슨은 사라지지 않고 이번 주 목록에 함께 남는다.
"""

import sqlite3

from app import db
from app.program import lessons, tiers


def ensure_week(con: sqlite3.Connection, athlete_id: int) -> str:
    week = db.week_start()
    if con.execute("SELECT 1 FROM lesson_assignments WHERE athlete_id = ? AND week_start = ?", (athlete_id, week)).fetchone():
        return week
    row = tiers.current(con, athlete_id)
    count = tiers.tier_setting(con, row["tier"] if row else None).lessons_per_week
    done = {r["lesson_id"] for r in con.execute("SELECT lesson_id FROM lesson_assignments WHERE athlete_id = ?", (athlete_id,))}
    for lesson_id in [i for i in lessons.curriculum() if i not in done][:count]:
        # 같은 주 첫 접속 요청이 동시에 두 번 와도 겹쳐 넣지 않는다
        con.execute("INSERT OR IGNORE INTO lesson_assignments (athlete_id, lesson_id, week_start) VALUES (?, ?, ?)", (athlete_id, lesson_id, week))
    return week


def this_week(con: sqlite3.Connection, athlete_id: int, week: str) -> list[sqlite3.Row]:
    """못 들은 레슨 전부 + 이번 주에 들은 레슨, 커리큘럼 순서."""
    rows = con.execute("""SELECT lesson_id, completed_at FROM lesson_assignments
                          WHERE athlete_id = ? AND (completed_at IS NULL OR completed_at >= ?)""", (athlete_id, week)).fetchall()
    order = {lid: i for i, lid in enumerate(lessons.curriculum())}
    return sorted(rows, key=lambda r: order.get(r["lesson_id"], 10**6))
