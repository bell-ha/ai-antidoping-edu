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
