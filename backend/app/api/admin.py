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
from app.model.adapter import MODEL_LABEL, SOURCE
from app.schemas import (AthleteCreate, AthleteDetail, AthleteRow, AthleteUpdate, ChatLog, ChecklistItem, ChecklistVisibility, IssuedCode, LessonLog,
                         LessonReview, OnboardingDone, Overview, ProgramSettings, QuizLog, RecordInput, StartChecklist)

router = APIRouter(prefix="/api/admin", dependencies=[Depends(admin)])
CODE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # 헷갈리는 글자(l·1·o·0·i) 뺌


def new_code(number: str) -> str:
    return f"{number}-{''.join(secrets.choice(CODE_ALPHABET) for _ in range(8))}"


def _rows(con: sqlite3.Connection, athlete_id: int | None = None) -> list[AthleteRow]:
    where = "WHERE a.id = :id" if athlete_id else "WHERE a.active = 1"
    args = {"id": athlete_id, "week": db.week_start()}
    out = []
    for a in con.execute(f"""
        SELECT a.id, a.number, a.name, a.sex, a.birth_year, a.active,
          (SELECT COUNT(*) FROM records r WHERE r.athlete_id = a.id) AS n_records,
          (SELECT body_weight FROM records r WHERE r.athlete_id = a.id ORDER BY date DESC, id DESC LIMIT 1) AS last_bw,
          (SELECT COUNT(*) FROM lesson_assignments l WHERE l.athlete_id = a.id AND l.completed_at IS NOT NULL) AS done,
          (SELECT COUNT(*) FROM quiz_attempts q WHERE q.athlete_id = a.id AND q.correct = 1) AS qc,
          (SELECT COUNT(*) FROM quiz_attempts q WHERE q.athlete_id = a.id AND q.correct = 0) AS qw,
          (SELECT COUNT(*) FROM chat_logs c WHERE c.athlete_id = a.id) AS nq,
          (SELECT MAX(first_at) FROM visits v WHERE v.athlete_id = a.id) AS last_visit,
          o.outcome AS onb, o.at AS onb_at,
          (SELECT COUNT(*) FROM lesson_assignments l WHERE l.athlete_id = a.id AND (l.completed_at IS NULL OR l.completed_at >= :week)) AS wk_total,
          (SELECT COUNT(*) FROM lesson_assignments l WHERE l.athlete_id = a.id AND l.completed_at >= :week) AS wk_done
        FROM athletes a LEFT JOIN onboarding o ON o.role = 'athlete' AND o.user_id = a.id AND o.kind = 'intro'
        {where} ORDER BY a.id""", args):
        t = tiers.current(con, a["id"])
        latest = tiers.latest_model(con, a["id"])
        out.append(AthleteRow(
            id=a["id"], number=a["number"], name=a["name"], birth_year=a["birth_year"],
            weight_class=predict.weight_class(a["sex"], a["last_bw"]) if a["last_bw"] else None,
            tier=t["tier"] if t else None, rank=t["rank"] if t else None,
            residual=latest[1].residual_observed_minus_predicted if latest else None,
            records=a["n_records"], lessons_completed=a["done"], quiz_correct=a["qc"], quiz_wrong=a["qw"],
            wrong_open=len(quiz.wrong_open(con, a["id"])), questions=a["nq"], last_visit=a["last_visit"],
            onboarding=a["onb"], onboarding_at=a["onb_at"], week_done=a["wk_done"], week_total=a["wk_total"], active=bool(a["active"])))
    return out


@router.get("/overview", response_model=Overview)
def overview() -> Overview:
    with db.connect() as con:
        rows = _rows(con)
        settings = tiers.load_settings(con)
    p = predict.params()
    model = p.get("model", "synthetic_trend")
    return Overview(athletes=rows, settings=settings, model_version=f"{model} ({p['source']})",
                    model_label=MODEL_LABEL[SOURCE.get(model, "synthetic")])


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


@router.patch("/athletes/{athlete_id}", response_model=AthleteDetail)
def update(athlete_id: int, body: AthleteUpdate) -> AthleteDetail:
    """이름 고치기, 보관(목록·줄 세우기에서 빼고 로그인을 막음)과 되돌리기. 기록은 지우지 않는다."""
    with db.connect() as con:
        _exists(con, athlete_id)
        if body.name is not None:
            con.execute("UPDATE athletes SET name = ? WHERE id = ?", (body.name.strip(), athlete_id))
        if body.active is not None:
            con.execute("UPDATE athletes SET active = ? WHERE id = ?", (int(body.active), athlete_id))
            tiers.rank_all(con)
    return detail(athlete_id)


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
        birth = con.execute("SELECT birth_year FROM athletes WHERE id = ?", (athlete_id,)).fetchone()["birth_year"]
        if int(body.date[:4]) < birth + 8:  # 1900-01 같은 오타가 '이전 대회'로 모델에 들어가던 문제(테스터 2)
            raise HTTPException(422, f"대회 연월이 출생연도({birth}년)와 맞지 않아요. 연도를 확인해 주세요.")
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
    "quizzes": "퀴즈 풀이 전부(교육 퀴즈·깜짝 퀴즈·다시 풀기)",
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
            header = ["번호", "이름", "출생연도", "체급", "단계", "순위", "실제 합계(kg)", "예측 합계(kg)", "관측-예측(kg)", "예측에 쓴 대회 수",
                      "모델", "계산 시각", "대회 기록 수", "이수", "이번 주 완료", "이번 주 목록", "퀴즈 정답", "퀴즈 오답", "오답 남음",
                      "질문 수", "마지막 접속일", "첫 안내", "첫 안내 시각"]
            onb = {"finished": "끝까지 봄", "skipped": "건너뜀"}
            rows = []
            for a in _rows(con):
                m = tiers.latest_model(con, a.id)
                r = m[1] if m else None
                at = con.execute("SELECT computed_at FROM model_results WHERE id = ?", (m[0],)).fetchone()[0] if m else ""
                rows.append([a.number, a.name, a.birth_year, _wc(a.weight_class), a.tier, a.rank,
                             r.observed.value if r else "", r.prediction.value if r else "",
                             r.residual_observed_minus_predicted if r else "", r.history_count if r else "",
                             r.model_version if r else "", at, a.records, a.lessons_completed, a.week_done, a.week_total,
                             a.quiz_correct, a.quiz_wrong, a.wrong_open, a.questions, (a.last_visit or "")[:10],
                             onb.get(a.onboarding or "", "아직"), a.onboarding_at or ""])
        elif kind == "quizzes":
            header = ["번호", "이름", "풀 때 단계", "지금 단계", "교육", "대분류", "종류", "고른 답", "정답 여부", "시각"]
            label = {"lesson": "교육 퀴즈", "surprise": "깜짝 퀴즈", "review": "오답 다시 풀기", "retry": "이수 후 다시 풀기"}
            rows = [[r["number"], r["name"], r["tier"] if r["tier"] is not None else "", _tier(con, r["athlete_id"]), r["lesson_id"],
                     _category(r["lesson_id"]), label.get(r["context"], r["context"]),
                     r["choice"], int(r["correct"]), r["at"]]
                    for r in con.execute("""SELECT a.number, a.name, q.* FROM quiz_attempts q JOIN athletes a ON a.id = q.athlete_id
                                            ORDER BY q.id""")]
        elif kind == "lessons":
            header = ["번호", "이름", "배정 때 단계", "지금 단계", "교육", "대분류", "배정 주", "이수 시각"]
            rows = [[r["number"], r["name"], r["tier"] if r["tier"] is not None else "", _tier(con, r["athlete_id"]), r["lesson_id"],
                     _category(r["lesson_id"]), r["week_start"],
                     r["completed_at"] or ""]
                    for r in con.execute("""SELECT a.number, a.name, l.* FROM lesson_assignments l JOIN athletes a ON a.id = l.athlete_id
                                            ORDER BY l.athlete_id, l.id""")]
        elif kind == "chats":
            header = ["번호", "이름", "시각", "질문", "답", "종류"]
            rows = [[r["number"] or "관리자", r["name"] or "", r["at"], r["question"], r["answer"], r["kind"]]
                    for r in con.execute("""SELECT a.number, a.name, c.* FROM chat_logs c LEFT JOIN athletes a ON a.id = c.athlete_id
                                            ORDER BY c.id""")]
        else:
            header = ["기록 id", "번호", "이름", "대회 연월", "대회", "계체", "체급", "인상", "용상", "합계"]
            rows = []
            for a in con.execute("SELECT id, number, name FROM athletes ORDER BY id").fetchall():
                rows += [[r.id, a["number"], a["name"], r.date, CATEGORY_KO.get(r.competition_category, r.competition_category), r.body_weight,
                          _wc(r.weight_class), r.snatch, r.clean_jerk, r.total] for r in tiers.records(con, a["id"])]
    stamp = db.today()
    return Response(_csv(header, rows), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{kind}-{stamp}.csv"'})


CATEGORY_KO = {"world": "세계대회", "continent": "대륙대회", "other_international": "기타 국제대회", "domestic": "국내대회"}


def _wc(weight_class: int | None) -> str:
    """체급 상한 없음(999)을 숫자 999로 내보내면 분석에서 999kg으로 읽힌다(테스터 2·3) → "+109"."""
    return "" if weight_class is None else ("+109" if weight_class >= 999 else str(weight_class))


def _tier(con: sqlite3.Connection, athlete_id: int) -> int | None:
    t = tiers.current(con, athlete_id)
    return t["tier"] if t else None


def _category(lesson_id: str) -> str:
    return lessons.meta(lesson_id)["category"] if lessons.exists(lesson_id) else ""


# ---------- 사람 검토(교육 자료 화면) ----------
# 화면에서 누른 표시는 운영 DB에만 남는다. 레슨 파일의 reviewed: true는 사람이 scripts/apply_reviews.py로 반영한다.

@router.get("/reviews", response_model=dict[str, LessonReview])
def reviews() -> dict[str, LessonReview]:
    with db.connect() as con:
        return {r["lesson_id"]: LessonReview(status=r["status"], note=r["note"], at=r["at"])
                for r in con.execute("SELECT * FROM lesson_reviews")}


@router.put("/reviews/{lesson_id}", response_model=LessonReview)
def set_review(lesson_id: str, body: LessonReview, request: Request) -> LessonReview:
    if not lessons.exists(lesson_id):
        raise HTTPException(404, "교육을 찾지 못했어요.")
    with db.connect() as con:
        if body.status == "none":
            con.execute("DELETE FROM lesson_reviews WHERE lesson_id = ?", (lesson_id,))
            return LessonReview(status="none")
        at = db.now_iso()
        con.execute("""INSERT INTO lesson_reviews (lesson_id, status, note, admin_id, at) VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(lesson_id) DO UPDATE SET status = excluded.status, note = excluded.note,
                       admin_id = excluded.admin_id, at = excluded.at""",
                    (lesson_id, body.status, (body.note or "").strip() or None, admin_id(request), at))
    return LessonReview(status=body.status, note=body.note, at=at)


@router.get("/checklist", response_model=StartChecklist)
def checklist(request: Request) -> StartChecklist:
    """관리자 시작 체크리스트. 각 항목이 끝났는지는 실제 데이터로 정한다(체크를 따로 저장하지 않음)."""
    with db.connect() as con:
        n = lambda sql: con.execute(sql).fetchone()[0]  # noqa: E731
        athletes = n("SELECT COUNT(*) FROM athletes WHERE active = 1")
        with_records = n("SELECT COUNT(DISTINCT r.athlete_id) FROM records r JOIN athletes a ON a.id = r.athlete_id WHERE a.active = 1")
        tiered = n("SELECT COUNT(*) FROM tier_assignments WHERE batch = (SELECT MAX(batch) FROM tier_assignments)")
        settings_saved = n("SELECT COUNT(*) FROM settings WHERE changed_by IS NOT NULL")
        reviewed = n("SELECT COUNT(*) FROM lesson_reviews")
        seen = {r["kind"] for r in con.execute("SELECT kind FROM onboarding WHERE role = 'admin' AND user_id = ?",
                                                (admin_id(request) or 0,))}
    total = len(lessons.curriculum())
    return StartChecklist(hidden="checklist" in seen, intro_done="intro" in seen, items=[
        ChecklistItem(key="athletes", label="선수 등록", done=athletes > 0, detail=f"{athletes}명 · 등록하면 로그인 코드가 나와요",
                      link="/admin"),
        ChecklistItem(key="records", label="경기 기록 입력", done=athletes > 0 and with_records == athletes,
                      detail=f"기록이 있는 선수 {with_records} / {athletes}명 · 선수를 눌러 상세에서 넣어요", link=""),
        ChecklistItem(key="tiers", label="단계 계산(자동)", done=tiered > 0,
                      detail=f"{tiered}명 배정 · 기록을 넣거나 지우면 모델이 돌고 자동으로 다시 나눠요", link=""),
        ChecklistItem(key="settings", label="단계 설정 확인", done=settings_saved > 0,
                      detail="단계 수와 단계별 주당 교육 수·퀴즈 빈도를 확인하고 저장", link="/admin/settings"),
        ChecklistItem(key="reviews", label="교육 자료 검토", done=reviewed >= total, detail=f"{reviewed} / {total}개 검토(모두 검토하면 완료)",
                      link="/library"),
    ])


@router.post("/onboarding", status_code=204)
def onboarding(body: OnboardingDone, request: Request) -> None:
    """관리자 첫 안내. 처음 기록만 남긴다."""
    with db.connect() as con:
        con.execute("INSERT OR IGNORE INTO onboarding (role, user_id, kind, outcome, at) VALUES ('admin', ?, 'intro', ?, ?)",
                    (admin_id(request) or 0, body.outcome, db.now_iso()))


@router.put("/checklist", response_model=ChecklistVisibility)
def set_checklist(body: ChecklistVisibility, request: Request) -> ChecklistVisibility:
    who = admin_id(request) or 0
    with db.connect() as con:
        if body.hidden:
            con.execute("INSERT OR IGNORE INTO onboarding (role, user_id, kind, outcome, at) VALUES ('admin', ?, 'checklist', 'hidden', ?)",
                        (who, db.now_iso()))
        else:
            con.execute("DELETE FROM onboarding WHERE role = 'admin' AND user_id = ? AND kind = 'checklist'", (who,))
    return body
