"""교육 프로그램: 로그인·권한, 줄 세우기·단계, 주간 배정, 퀴즈, 관리자 기능."""

import random

from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.program import lessons, quiz, tiers, weekly
from app.schemas import ProgramSettings


# ---------- 로그인·권한 ----------

def test_login_by_code_gives_role(people):
    c = TestClient(app)
    assert c.post("/api/session", json={"code": "WL-001-test"}).json()["role"] == "athlete"
    assert c.post("/api/session", json={"code": "ADMIN-test0001"}).json()["role"] == "admin"
    assert c.post("/api/session", json={"code": "wrong"}).status_code == 401


def test_code_guessing_is_throttled(people):
    c = TestClient(app)
    for _ in range(10):
        c.post("/api/session", json={"code": "wrong"})
    assert c.post("/api/session", json={"code": "WL-001-test"}).status_code == 429


def test_athlete_cannot_open_admin_and_admin_cannot_open_athlete(people):
    assert people.login("athlete").get("/api/admin/overview").status_code == 403
    assert people.login("admin").get("/api/athlete/home").status_code == 403


def test_reissued_code_ends_old_session(people):
    a = people.login("athlete")
    people.login("admin").post(f"/api/admin/athletes/{people.athlete_ids[0]}/code")
    assert a.get("/api/athlete/home").status_code == 401


# ---------- 줄 세우기 ----------

def test_bigger_rise_over_prediction_ranks_higher_and_no_result_is_lowest(people):
    with db.connect() as con:
        rows = {i: tiers.current(con, i) for i in people.athlete_ids}
    up_big, up_small, flat, down, one_record = people.athlete_ids
    assert rows[up_big]["rank"] < rows[up_small]["rank"] < rows[flat]["rank"] < rows[down]["rank"]
    assert rows[one_record]["rank"] == 5 and rows[one_record]["tier"] == 1 and rows[up_big]["tier"] == 5


def test_tiers_split_evenly():
    with db.connect() as con:
        con.execute("INSERT INTO admins (name, code_hash, created_at) VALUES ('a', 'h', 'now')")
        for i in range(100):
            con.execute("INSERT INTO athletes (number, name, birth_year, code_hash, created_at) VALUES (?, 'x', 2000, ?, 'now')",
                        (f"WL-{i:03d}", f"h{i}"))
        batch = tiers.rank_all(con)
        counts = [r[0] for r in con.execute("SELECT COUNT(*) FROM tier_assignments WHERE batch = ? GROUP BY tier", (batch,))]
    assert counts == [20] * 5


def test_settings_change_tier_count_and_reranks(people):
    admin = people.login("admin")
    body = {"tiers": [{"tier": 1, "lessons_per_week": 2, "quiz_probability": 0, "quiz_questions": 1},
                      {"tier": 2, "lessons_per_week": 4, "quiz_probability": 1, "quiz_questions": 2}]}
    overview = admin.put("/api/admin/settings", json=body).json()
    assert len(overview["settings"]["tiers"]) == 2 and {a["tier"] for a in overview["athletes"]} == {1, 2}


# ---------- 주간 배정 ----------

def test_week_assigns_tier_count_in_curriculum_order(people):
    top = people.athlete_ids[0]  # 5단계 = 주 15개
    with db.connect() as con:
        week = weekly.ensure_week(con, top)
        got = [r["lesson_id"] for r in weekly.this_week(con, top, week)]
    assert got == lessons.curriculum()[:15]


def test_unfinished_lessons_carry_over(people):
    low = people.athlete_ids[4]  # 1단계 = 주 3개
    with db.connect() as con:
        weekly.ensure_week(con, low)
        con.execute("UPDATE lesson_assignments SET week_start = '2000-01-03' WHERE athlete_id = ?", (low,))  # 지난주 배정으로
        week = weekly.ensure_week(con, low)
        got = weekly.this_week(con, low, week)
    assert len(got) == 6


# ---------- 레슨·퀴즈 ----------

def test_lesson_hides_answer_and_answering_completes_it(people):
    a = people.login("athlete")
    home = a.get("/api/athlete/home").json()
    lid = home["lessons"][0]["lesson_id"]
    view = a.get(f"/api/athlete/lessons/{lid}").json()
    assert "answer" not in view["quiz"] and view["sections"]
    right = lessons.meta(lid)["quiz"]["answer"]
    r = a.post(f"/api/athlete/lessons/{lid}/answer", json={"lesson_id": lid, "choice": right}).json()
    assert r["correct"] and a.get("/api/athlete/home").json()["completed_total"] == 1


def test_unassigned_lesson_can_be_read_and_counts_when_answered(people):
    """질문하기에서 추천된 레슨(이번 주 목록 밖)도 읽고 퀴즈를 풀면 이수로 남는다."""
    a = people.login("athlete")
    assert a.get("/api/athlete/lessons/M-010").json()["completed"] is False
    a.post("/api/athlete/lessons/M-010/answer", json={"lesson_id": "M-010", "choice": 1})
    home = a.get("/api/athlete/home").json()
    assert home["completed_total"] == 1 and len([l for l in home["lessons"] if not l["completed"]]) == 15
    assert a.get("/api/athlete/lessons/none").status_code == 404


def test_surprise_quiz_only_from_learned_lessons_wrong_first(people):
    aid = people.athlete_ids[0]
    with db.connect() as con:
        weekly.ensure_week(con, aid)
        learned = lessons.curriculum()[:4]
        con.execute(f"UPDATE lesson_assignments SET completed_at = 'x' WHERE athlete_id = ? AND lesson_id IN ({','.join('?' * 4)})",
                    (aid, *learned))
        quiz.answer(con, aid, learned[2], 9 - 5 if lessons.meta(learned[2])["quiz"]["answer"] != 4 else 1, "lesson")  # 틀림
        tiers.save_settings(con, ProgramSettings(tiers=[{"tier": i, "lessons_per_week": 15, "quiz_probability": 1.0, "quiz_questions": 3}
                                                         for i in range(1, 6)]), None)
        quiz.roll_surprise(con, aid, random.Random(1))
        pending = [q.lesson_id for q in quiz.pending(con, aid)]
    assert len(pending) == 3 and set(pending) <= set(learned) and pending[0] == learned[2]


def test_surprise_quiz_never_without_learned_lessons(people):
    aid = people.athlete_ids[0]
    with db.connect() as con:
        quiz.roll_surprise(con, aid, random.Random(1))
        assert quiz.pending(con, aid) == []


def test_admin_sees_progress(people):
    a = people.login("athlete")
    lid = a.get("/api/athlete/home").json()["lessons"][0]["lesson_id"]
    a.post(f"/api/athlete/lessons/{lid}/answer", json={"lesson_id": lid, "choice": 1})
    row = next(r for r in people.login("admin").get("/api/admin/overview").json()["athletes"] if r["id"] == people.athlete_ids[0])
    assert row["lessons_completed"] == 1 and row["quiz_correct"] + row["quiz_wrong"] == 1 and row["last_visit"]


# ---------- 관리자: 선수 등록·기록 ----------

def test_create_athlete_issues_code_once(people):
    admin = people.login("admin")
    issued = admin.post("/api/admin/athletes", json={"name": "새선수", "birth_year": 2005}).json()
    assert issued["number"] == "WL-006"
    assert TestClient(app).post("/api/session", json={"code": issued["code"]}).json()["label"] == "새선수"
    with db.connect() as con:
        assert issued["code"] not in str([tuple(r) for r in con.execute("SELECT * FROM athletes")])  # 원문은 저장 안 함


def test_adding_record_reruns_model_and_reranks(people):
    admin = people.login("admin")
    low = people.athlete_ids[4]
    for month, total in [("2025-08", 250), ("2025-09", 252), ("2025-10", 330)]:
        s = round(total * 0.45)
        d = admin.post(f"/api/admin/athletes/{low}/records",
                       json={"date": month, "competition_category": "domestic", "body_weight": 72.5, "snatch": s, "clean_jerk": total - s}).json()
    assert d["model_result"]["residual_observed_minus_predicted"] > 0 and d["athlete"]["tier"] > 1


def test_future_record_is_rejected(people):
    r = people.login("admin").post(f"/api/admin/athletes/{people.athlete_ids[0]}/records",
                                   json={"date": "2999-01", "competition_category": "domestic", "body_weight": 72, "snatch": 100, "clean_jerk": 120})
    assert r.status_code == 422


def test_demo_codes_only_in_demo_mode(monkeypatch, tmp_path):
    from app import config
    (tmp_path / "dummy_codes.csv").write_text("number,name,role,code\nADMIN,관리자,admin,ADMIN-x\n", encoding="utf-8")
    monkeypatch.setattr(config, "APP_DB", tmp_path / "app.sqlite")
    c = TestClient(app)
    assert c.get("/api/demo/codes").json()[0]["code"] == "ADMIN-x"
    monkeypatch.setattr(config, "DEMO_MODE", False)
    assert c.get("/api/demo/codes").status_code == 404


def test_unanswered_surprise_quiz_does_not_pile_up(people):
    aid = people.athlete_ids[0]
    with db.connect() as con:
        weekly.ensure_week(con, aid)
        con.execute("UPDATE lesson_assignments SET completed_at = 'x' WHERE athlete_id = ?", (aid,))
        tiers.save_settings(con, ProgramSettings(tiers=[{"tier": i, "lessons_per_week": 15, "quiz_probability": 1.0, "quiz_questions": 3}
                                                         for i in range(1, 6)]), None)
        quiz.roll_surprise(con, aid, random.Random(1))
        quiz.roll_surprise(con, aid, random.Random(2))  # 다음 날
        assert len(quiz.pending(con, aid)) == 3


def test_week_assignment_is_idempotent(people):
    aid = people.athlete_ids[0]
    with db.connect() as con:
        con.execute("INSERT INTO lesson_assignments (athlete_id, lesson_id, week_start) VALUES (?, ?, ?)", (aid, lessons.curriculum()[0], "2000-01-03"))
        weekly.ensure_week(con, aid)
        weekly.ensure_week(con, aid)
        n = con.execute("SELECT COUNT(*) FROM lesson_assignments WHERE athlete_id = ?", (aid,)).fetchone()[0]
    assert n == 16


def test_blank_name_is_rejected(people):
    assert people.login("admin").post("/api/admin/athletes", json={"name": "   ", "birth_year": 2005}).status_code == 422


# ---------- 내 학습 기록 · 오답 다시 풀기 · CSV ----------

def _wrong_choice(lesson_id: str) -> int:
    return 1 if lessons.meta(lesson_id)["quiz"]["answer"] != 1 else 2


def test_history_and_wrong_answer_review(people):
    a = people.login("athlete")
    lids = [l["lesson_id"] for l in a.get("/api/athlete/home").json()["lessons"][:2]]
    a.post(f"/api/athlete/lessons/{lids[0]}/answer", json={"lesson_id": lids[0], "choice": _wrong_choice(lids[0])})
    a.post(f"/api/athlete/lessons/{lids[1]}/answer", json={"lesson_id": lids[1], "choice": lessons.meta(lids[1])["quiz"]["answer"]})
    h = a.get("/api/athlete/history").json()
    assert h["completed"] == 2 and [w["lesson_id"] for w in h["wrong"]] == [lids[0]] and "answer" not in h["wrong"][0]
    assert people.login("admin").get(f"/api/admin/athletes/{people.athlete_ids[0]}").json()["athlete"]["wrong_open"] == 1
    r = a.post("/api/athlete/review/answer", json={"lesson_id": lids[0], "choice": lessons.meta(lids[0])["quiz"]["answer"]}).json()
    assert r["correct"] and a.get("/api/athlete/history").json()["wrong"] == []
    quizzes = people.login("admin").get(f"/api/admin/athletes/{people.athlete_ids[0]}").json()["quizzes"]
    assert quizzes[0]["context"] == "review"


def test_review_only_for_completed_lessons(people):
    assert people.login("athlete").post("/api/athlete/review/answer", json={"lesson_id": "A-001", "choice": 1}).status_code == 404


def test_csv_export(people):
    admin = people.login("admin")
    r = admin.get("/api/admin/export/athletes.csv")
    assert r.status_code == 200 and r.text.startswith("﻿번호,이름") and "WL-001" in r.text and "test" not in r.text.lower().split("\n")[0]
    for kind in ("quizzes", "lessons", "chats", "records"):
        assert admin.get(f"/api/admin/export/{kind}.csv").status_code == 200
    assert admin.get("/api/admin/export/codes.csv").status_code == 404
    assert people.login("athlete").get("/api/admin/export/athletes.csv").status_code == 403
