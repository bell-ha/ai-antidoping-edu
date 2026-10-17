"""선수 화면: 교육 시작하기 · 갑자기 퀴즈 (D37). 질문하기는 api/chat.py."""

from fastapi import APIRouter, Depends, HTTPException

from app import config, db
from app.api.login import athlete
from app.program import lessons, quiz, weekly
from app.schemas import AthleteHome, LessonCard, LessonView, QuizAnswer, QuizResult, SessionInfo, Survey

router = APIRouter(prefix="/api/athlete")


@router.get("/home", response_model=AthleteHome)
def home(who: SessionInfo = Depends(athlete)) -> AthleteHome:
    """접속할 때마다 부른다: 이번 주 배정(없으면 만듦), 그날 첫 접속이면 갑자기 퀴즈 추첨."""
    with db.connect() as con:
        week = weekly.ensure_week(con, who.athlete_id)
        if quiz.first_visit_today(con, who.athlete_id):
            quiz.roll_surprise(con, who.athlete_id)
        rows = weekly.this_week(con, who.athlete_id, week)
        done = con.execute("SELECT COUNT(*) FROM lesson_assignments WHERE athlete_id = ? AND completed_at IS NOT NULL",
                           (who.athlete_id,)).fetchone()[0]
        surprise = quiz.pending(con, who.athlete_id)
    cards = [LessonCard(lesson_id=r["lesson_id"], title=lessons.title(r["lesson_id"]),
                        category=lessons.meta(r["lesson_id"])["category"], completed=r["completed_at"] is not None)
             for r in rows if lessons.exists(r["lesson_id"])]
    return AthleteHome(name=who.label, week_start=week, lessons=cards, completed_total=done,
                       lesson_total=len(lessons.curriculum()), surprise_quiz=surprise)


def _assignment(con, athlete_id: int, lesson_id: str):
    row = con.execute("SELECT completed_at FROM lesson_assignments WHERE athlete_id = ? AND lesson_id = ?",
                      (athlete_id, lesson_id)).fetchone()
    if row is None or not lessons.exists(lesson_id):
        raise HTTPException(404, "배정된 교육이 아니에요.")
    return row


@router.get("/lessons/{lesson_id}", response_model=LessonView)
def lesson(lesson_id: str, who: SessionInfo = Depends(athlete)) -> LessonView:
    with db.connect() as con:
        row = _assignment(con, who.athlete_id, lesson_id)
    m = lessons.meta(lesson_id)
    return LessonView(lesson_id=lesson_id, title=m["title"], category=m["category"], sections=lessons.sections(lesson_id),
                      quiz=lessons.question(lesson_id), completed=row["completed_at"] is not None)


@router.post("/lessons/{lesson_id}/answer", response_model=QuizResult)
def lesson_answer(lesson_id: str, body: QuizAnswer, who: SessionInfo = Depends(athlete)) -> QuizResult:
    """레슨 끝 퀴즈. 답하면(맞든 틀리든) 그 레슨은 이수."""
    with db.connect() as con:
        _assignment(con, who.athlete_id, lesson_id)
        result = quiz.answer(con, who.athlete_id, lesson_id, body.choice, "lesson")
        con.execute("UPDATE lesson_assignments SET completed_at = COALESCE(completed_at, ?) WHERE athlete_id = ? AND lesson_id = ?",
                    (db.now_iso(), who.athlete_id, lesson_id))
    return result


@router.post("/quiz/answer", response_model=QuizResult)
def surprise_answer(body: QuizAnswer, who: SessionInfo = Depends(athlete)) -> QuizResult:
    with db.connect() as con:
        result = quiz.answer_surprise(con, who.athlete_id, body.lesson_id, body.choice)
    if result is None:
        raise HTTPException(404, "풀 퀴즈가 없어요.")
    return result


@router.get("/survey", response_model=Survey)
def survey(who: SessionInfo = Depends(athlete)) -> Survey:
    """외부 설문 링크(SURVEY_URL의 "{pid}" 자리에 선수 번호)."""
    url = config.SURVEY_URL
    if not url.startswith("https://") or "{pid}" not in url:
        raise HTTPException(404)
    with db.connect() as con:
        number = con.execute("SELECT number FROM athletes WHERE id = ?", (who.athlete_id,)).fetchone()["number"]
    return Survey(url=url.replace("{pid}", number))
