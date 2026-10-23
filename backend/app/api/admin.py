"""관리자 화면: 선수 목록·상세, 선수 등록과 코드 발급, 경기 기록 입력, 단계 설정, CSV 내보내기.

기록을 넣거나 지우면 그 선수의 모델을 다시 돌리고 전원을 다시 줄 세운다. 단계 설정을 바꿔도 다시 줄 세운다.
"""

import csv
import io
import secrets
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from app import db
from app.api.login import admin, admin_id
from app.model import predict
from app.program import lessons, quiz, tiers
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
            wrong_open=len(quiz.wrong_open(con, a["id"])), questions=a["nq"], last_visit=a["last_visit"]))
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


# ---------- CSV 내보내기(논문 분석용) ----------
# 엑셀에서 한글이 깨지지 않게 UTF-8 BOM을 붙인다. 로그인 코드(해시 포함)는 내보내지 않는다.
EXPORTS = {
    "athletes": "선수별 요약(단계·관측−예측·이수·퀴즈·오답 남음·질문·마지막 접속일)",
    "quizzes": "퀴즈 풀이 전부(교육 퀴즈·갑자기 퀴즈·다시 풀기)",
    "lessons": "교육 배정과 이수",
    "chats": "질문과 답",
    "records": "경기 기록과 체급",
}


def _csv(header: list[str], rows: list[list]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    return "\ufeff" + buf.getvalue()


@router.get("/export/{kind}.csv")
def export(kind: str) -> Response:
    if kind not in EXPORTS:
        raise HTTPException(404, "내보낼 수 없는 종류예요.")
    with db.connect() as con:
        if kind == "athletes":
            header = ["번호", "이름", "출생연도", "체급", "단계", "순위", "관측-예측(kg)", "기록 수", "이수", "퀴즈 정답", "퀴즈 오답",
                      "오답 남음", "질문 수", "마지막 접속일"]
            rows = [[a.number, a.name, a.birth_year, a.weight_class, a.tier, a.rank, a.residual, a.records, a.lessons_completed,
                     a.quiz_correct, a.quiz_wrong, a.wrong_open, a.questions, (a.last_visit or "")[:10]] for a in _rows(con)]
        elif kind == "quizzes":
            header = ["번호", "이름", "단계", "교육", "대분류", "종류", "고른 답", "정답 여부", "시각"]
            label = {"lesson": "교육 퀴즈", "surprise": "갑자기 퀴즈", "review": "다시 풀기"}
            rows = [[r["number"], r["name"], _tier(con, r["athlete_id"]), r["lesson_id"], _category(r["lesson_id"]), label.get(r["context"], r["context"]),
                     r["choice"], int(r["correct"]), r["at"]]
                    for r in con.execute("""SELECT a.number, a.name, q.* FROM quiz_attempts q JOIN athletes a ON a.id = q.athlete_id
                                            ORDER BY q.id""")]
        elif kind == "lessons":
            header = ["번호", "이름", "단계", "교육", "대분류", "배정 주", "이수 시각"]
            rows = [[r["number"], r["name"], _tier(con, r["athlete_id"]), r["lesson_id"], _category(r["lesson_id"]), r["week_start"],
                     r["completed_at"] or ""]
                    for r in con.execute("""SELECT a.number, a.name, l.* FROM lesson_assignments l JOIN athletes a ON a.id = l.athlete_id
                                            ORDER BY l.athlete_id, l.id""")]
        elif kind == "chats":
            header = ["번호", "이름", "시각", "질문", "답", "종류"]
            rows = [[r["number"] or "관리자", r["name"] or "", r["at"], r["question"], r["answer"], r["kind"]]
                    for r in con.execute("""SELECT a.number, a.name, c.* FROM chat_logs c LEFT JOIN athletes a ON a.id = c.athlete_id
                                            ORDER BY c.id""")]
        else:
            header = ["번호", "이름", "대회 날짜", "대회", "계체", "체급", "인상", "용상", "합계"]
            rows = []
            for a in con.execute("SELECT id, number, name FROM athletes ORDER BY id").fetchall():
                rows += [[a["number"], a["name"], r.date, r.competition_category, r.body_weight, r.weight_class, r.snatch, r.clean_jerk,
                          r.total] for r in tiers.records(con, a["id"])]
    stamp = db.today()
    return Response(_csv(header, rows), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{kind}-{stamp}.csv"'})


def _tier(con: sqlite3.Connection, athlete_id: int) -> int | None:
    t = tiers.current(con, athlete_id)
    return t["tier"] if t else None


def _category(lesson_id: str) -> str:
    return lessons.meta(lesson_id)["category"] if lessons.exists(lesson_id) else ""
