"""교육 자료 열람(관리자) — 레슨과 AI 검색이 같은 섹션 번호를 쓴다."""

from fastapi.testclient import TestClient

from app.chat.retrieve import _index
from app.main import app


def test_library_lists_every_lesson(people):
    docs = people.login("admin").get("/api/library").json()
    assert len(docs) == len({c.doc_id for c in _index().chunks}) == 300


def test_section_ids_match_chunk_ids(people):
    c = people.login("admin")
    doc = c.get("/api/library/G-005").json()
    assert [f"G-005#{s['id']}" for s in doc["sections"]] == [ch.id for ch in _index().chunks if ch.doc_id == "G-005"]


def test_library_is_admin_only(people):
    assert TestClient(app).get("/api/library").status_code == 401
    assert people.login("athlete").get("/api/library").status_code == 403
    assert people.login("admin").get("/api/library/none").status_code == 404


def test_admin_sees_quiz_with_answer_in_library(people):
    doc = people.login("admin").get("/api/library/G-005").json()
    assert doc["quiz"]["answer"] in (1, 2, 3, 4) and doc["quiz"]["explanation"]


def test_review_marks_are_saved_and_cleared(people):
    admin = people.login("admin")
    assert admin.put("/api/admin/reviews/G-005", json={"status": "needs_fix", "note": "기준치 표현 확인"}).status_code == 200
    assert admin.get("/api/admin/reviews").json()["G-005"]["note"] == "기준치 표현 확인"
    admin.put("/api/admin/reviews/G-005", json={"status": "reviewed"})
    assert admin.get("/api/admin/reviews").json()["G-005"]["status"] == "reviewed"
    admin.put("/api/admin/reviews/G-005", json={"status": "none"})
    assert "G-005" not in admin.get("/api/admin/reviews").json()
    assert admin.put("/api/admin/reviews/none", json={"status": "reviewed"}).status_code == 404
    assert people.login("athlete").get("/api/admin/reviews").status_code == 403
