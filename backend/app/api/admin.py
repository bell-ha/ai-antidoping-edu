"""관리자 화면 (D37): 선수 목록·상세, 선수 등록과 코드 발급, 경기 기록 입력, 단계 설정.

기록을 넣거나 지우면 그 선수의 모델을 다시 돌리고 전원을 다시 줄 세운다. 단계 설정을 바꿔도 다시 줄 세운다.
"""

import secrets
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request

from app import db
from app.api.login import admin, admin_id
from app.model import predict
from app.program import lessons, tiers
from app.schemas import (AthleteCreate, AthleteDetail, AthleteRow, ChatLog, IssuedCode, LessonLog,
                         Overview, ProgramSettings, QuizLog, RecordInput)

router = APIRouter(prefix="/api/admin", dependencies=[Depends(admin)])
CODE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # 헷갈리는 글자(l·1·o·0·i) 뺌


def new_code(number: str) -> str:
    return f"{number}-{''.join(secrets.choice(CODE_ALPHABET) for _ in range(8))}"


def _rows(con: sqlite3.Connection, athlete_id: int | None = None) -> list[AthleteRow]:
    where = "WHERE a.id = ?" if athlete_id else "WHERE a.active = 1"
    args = (athlete_id,) if athlete_id else ()
    out = []
    for a in con.execute(f"""
        SELECT a.id, a.number, a.name, a.sex, a.birth_year,
          (SELECT COUNT(*) FROM records r WHERE r.athlete_id = a.id) AS n_records,
          (SELECT body_weight FROM records r WHERE r.athlete_id = a.id ORDER BY date DESC, id DESC LIMIT 1) AS last_bw,
          (SELECT COUNT(*) FROM lesson_assignments l WHERE l.athlete_id = a.id AND l.completed_at IS NOT NULL) AS done,
          (SELECT COUNT(*) FROM quiz_attempts q WHERE q.athlete_id = a.id AND q.correct = 1) AS qc,
          (SELECT COUNT(*) FROM quiz_attempts q WHERE q.athlete_id = a.id AND q.correct = 0) AS qw,
          (SELECT COUNT(*) FROM chat_logs c WHERE c.athlete_id = a.id) AS nq,
          (SELECT MAX(first_at) FROM visits v WHERE v.athlete_id = a.id) AS last_visit
        FROM athletes a {where} ORDER BY a.id""", args):
        t = tiers.current(con, a["id"])
        latest = tiers.latest_model(con, a["id"])
        out.append(AthleteRow(
            id=a["id"], number=a["number"], name=a["name"], birth_year=a["birth_year"],
            weight_class=predict.weight_class(a["sex"], a["last_bw"]) if a["last_bw"] else None,
            tier=t["tier"] if t else None, rank=t["rank"] if t else None,
            residual=latest[1].residual_observed_minus_predicted if latest else None,
            records=a["n_records"], lessons_completed=a["done"], quiz_correct=a["qc"], quiz_wrong=a["qw"],
            questions=a["nq"], last_visit=a["last_visit"]))
    return out


@router.get("/overview", response_model=Overview)
def overview() -> Overview:
    with db.connect() as con:
        rows = _rows(con)
        settings = tiers.load_settings(con)
    p = predict.params()
    return Overview(athletes=rows, settings=settings, model_version=f"{p.get('model', 'synthetic_trend')} ({p['source']})")


def _exists(con: sqlite3.Connection, athlete_id: int) -> None:
    if not con.execute("SELECT 1 FROM athletes WHERE id = ?", (athlete_id,)).fetchone():
        raise HTTPException(404, "선수를 찾지 못했어요.")


@router.get("/athletes/{athlete_id}", response_model=AthleteDetail)
def detail(athlete_id: int) -> AthleteDetail:
    with db.connect() as con:
        _exists(con, athlete_id)
        row = _rows(con, athlete_id)[0]
        latest = tiers.latest_model(con, athlete_id)
        lessons_rows = con.execute("SELECT lesson_id, week_start, completed_at FROM lesson_assignments WHERE athlete_id = ? ORDER BY id",
                                   (athlete_id,)).fetchall()
        quizzes = con.execute("SELECT * FROM quiz_attempts WHERE athlete_id = ? ORDER BY id DESC", (athlete_id,)).fetchall()
        chats = con.execute("SELECT question, answer, at FROM chat_logs WHERE athlete_id = ? ORDER BY id DESC", (athlete_id,)).fetchall()
        records = tiers.records(con, athlete_id)
    return AthleteDetail(
        athlete=row, records=records, model_result=latest[1] if latest else None,
        lessons=[LessonLog(lesson_id=r["lesson_id"], title=lessons.title(r["lesson_id"]), week_start=r["week_start"],
                           completed_at=r["completed_at"]) for r in lessons_rows],
        quizzes=[QuizLog(lesson_id=q["lesson_id"], title=lessons.title(q["lesson_id"]), context=q["context"], choice=q["choice"],
                         correct=bool(q["correct"]), at=q["at"]) for q in quizzes],
        chats=[ChatLog(question=c["question"], answer=c["answer"], at=c["at"]) for c in chats])


@router.post("/athletes", response_model=IssuedCode)
def create(body: AthleteCreate) -> IssuedCode:
    with db.connect() as con:
        n = con.execute("SELECT COUNT(*) FROM athletes").fetchone()[0] + 1
        number = f"WL-{n:03d}"
        code = new_code(number)
        cur = con.execute("INSERT INTO athletes (number, name, birth_year, code_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                          (number, body.name.strip(), body.birth_year, db.code_hash(code), db.now_iso()))
        tiers.compute_model(con, cur.lastrowid)
        tiers.rank_all(con)
    return IssuedCode(athlete_id=cur.lastrowid, number=number, code=code)


@router.post("/athletes/{athlete_id}/code", response_model=IssuedCode)
def reissue(athlete_id: int) -> IssuedCode:
    """코드를 잃어버렸을 때. 이전 코드는 바로 못 쓴다."""
    with db.connect() as con:
        _exists(con, athlete_id)
        number = con.execute("SELECT number FROM athletes WHERE id = ?", (athlete_id,)).fetchone()["number"]
        code = new_code(number)
        con.execute("UPDATE athletes SET code_hash = ? WHERE id = ?", (db.code_hash(code), athlete_id))
    return IssuedCode(athlete_id=athlete_id, number=number, code=code)


@router.post("/athletes/{athlete_id}/records", response_model=AthleteDetail)
def add_record(athlete_id: int, body: RecordInput, request: Request) -> AthleteDetail:
    with db.connect() as con:
        _exists(con, athlete_id)
        con.execute("""INSERT INTO records (athlete_id, date, competition_category, body_weight, snatch, clean_jerk, entered_by, entered_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (athlete_id, body.date, body.competition_category, body.body_weight, body.snatch, body.clean_jerk,
                     admin_id(request), db.now_iso()))
        tiers.compute_model(con, athlete_id)
        tiers.rank_all(con)
    return detail(athlete_id)


@router.delete("/athletes/{athlete_id}/records/{record_id}", response_model=AthleteDetail)
def delete_record(athlete_id: int, record_id: int) -> AthleteDetail:
    with db.connect() as con:
        cur = con.execute("DELETE FROM records WHERE id = ? AND athlete_id = ?", (record_id, athlete_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "기록을 찾지 못했어요.")
        tiers.compute_model(con, athlete_id)
        tiers.rank_all(con)
    return detail(athlete_id)


@router.put("/settings", response_model=Overview)
def update_settings(body: ProgramSettings, request: Request) -> Overview:
    with db.connect() as con:
        tiers.save_settings(con, body, admin_id(request))
        tiers.rank_all(con)
    return overview()


@router.post("/rerank", response_model=Overview)
def rerank() -> Overview:
    """모든 선수의 모델을 지금 모델 파일로 다시 돌리고 다시 줄 세운다(모델 파일 내용을 바꿨을 때).
    읽어 둔 모델을 비우고 파일을 다시 읽는다. 모델 폴더 자체(private/models 유무)가 바뀌면 서버를 다시 켜야 한다."""
    predict.params.cache_clear()
    predict._rnn.cache_clear()
    with db.connect() as con:
        for r in con.execute("SELECT id FROM athletes WHERE active = 1").fetchall():
            tiers.compute_model(con, r["id"])
        tiers.rank_all(con)
    return overview()
