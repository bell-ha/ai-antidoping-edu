"""퀴즈: 레슨 직후 1문항, 갑자기 퀴즈(D37).

갑자기 퀴즈는 그날 첫 접속 때 단계별 확률로 나온다. 문항은 이미 배운 레슨에서만, 마지막에 틀린 레슨을 먼저.
"""

import random
import sqlite3

from app import db
from app.program import lessons, tiers
from app.schemas import QuizQuestion, QuizResult


def answer(con: sqlite3.Connection, athlete_id: int, lesson_id: str, choice: int, context: str) -> QuizResult:
    result = lessons.grade(lesson_id, choice)
    con.execute("INSERT INTO quiz_attempts (athlete_id, lesson_id, context, choice, correct, at) VALUES (?, ?, ?, ?, ?, ?)",
                (athlete_id, lesson_id, context, choice, int(result.correct), db.now_iso()))
    return result


def first_visit_today(con: sqlite3.Connection, athlete_id: int) -> bool:
    cur = con.execute("INSERT OR IGNORE INTO visits (athlete_id, day, first_at) VALUES (?, ?, ?)",
                      (athlete_id, db.today(), db.now_iso()))
    return cur.rowcount == 1


def roll_surprise(con: sqlite3.Connection, athlete_id: int, rng: random.Random | None = None) -> None:
    rng = rng or random.Random()
    row = tiers.current(con, athlete_id)
    setting = tiers.tier_setting(con, row["tier"] if row else None)
    if rng.random() >= setting.quiz_probability:
        return
    learned = [r["lesson_id"] for r in con.execute(
        "SELECT lesson_id FROM lesson_assignments WHERE athlete_id = ? AND completed_at IS NOT NULL", (athlete_id,))]
    if not learned:
        return
    last = {r["lesson_id"]: r["correct"] for r in con.execute(
        "SELECT lesson_id, correct FROM quiz_attempts WHERE athlete_id = ? ORDER BY id", (athlete_id,))}
    rng.shuffle(learned)
    learned.sort(key=lambda lid: last.get(lid, 1))  # 마지막에 틀린 것(0) 먼저
    for lesson_id in learned[:setting.quiz_questions]:
        con.execute("INSERT INTO surprise_quizzes (athlete_id, lesson_id, created_at) VALUES (?, ?, ?)",
                    (athlete_id, lesson_id, db.now_iso()))


def pending(con: sqlite3.Connection, athlete_id: int) -> list[QuizQuestion]:
    rows = con.execute("SELECT DISTINCT lesson_id FROM surprise_quizzes WHERE athlete_id = ? AND answered_at IS NULL ORDER BY id",
                       (athlete_id,)).fetchall()
    return [lessons.question(r["lesson_id"]) for r in rows if lessons.exists(r["lesson_id"])]


def answer_surprise(con: sqlite3.Connection, athlete_id: int, lesson_id: str, choice: int) -> QuizResult | None:
    open_rows = con.execute("SELECT id FROM surprise_quizzes WHERE athlete_id = ? AND lesson_id = ? AND answered_at IS NULL",
                            (athlete_id, lesson_id)).fetchall()
    if not open_rows:
        return None
    con.execute("UPDATE surprise_quizzes SET answered_at = ? WHERE athlete_id = ? AND lesson_id = ? AND answered_at IS NULL",
                (db.now_iso(), athlete_id, lesson_id))
    return answer(con, athlete_id, lesson_id, choice, "surprise")
