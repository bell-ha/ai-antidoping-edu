"""교육 레슨 형식: 텍스트 설명 + 객관식 퀴즈 1문항 (knowledge/education/README.md)."""

from app.config import EDUCATION
from app.chat.retrieve import parse, read_doc

LESSONS = sorted((EDUCATION / "lessons").rglob("*.md"))


def test_lessons_exist():
    assert LESSONS


def test_each_lesson_has_text_and_one_multiple_choice_quiz():
    ids = set()
    for path in LESSONS:
        meta, _ = read_doc(path)
        assert meta["doc_id"] == path.stem and meta["doc_id"] not in ids, path
        ids.add(meta["doc_id"])
        assert parse(path), f"본문 소제목(## ) 없음: {path}"
        q = meta["quiz"]
        assert len(q["choices"]) == 4 and len(set(q["choices"])) == 4, path
        assert 1 <= q["answer"] <= 4 and q["question"] and q["explanation"], path


def test_every_section_cites_a_source():
    missing = [c.id for p in LESSONS for c in parse(p) if "출처:" not in c.text]
    assert missing == []


def test_no_forbidden_words_in_lessons():
    from test_guard import FORBIDDEN
    hits = [f"{p.name}:{i}" for p in LESSONS for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if FORBIDDEN.search(line)]
    assert hits == []


def test_curriculum_has_all_300_in_category_order():
    from app.program import lessons
    order = lessons.curriculum()
    assert len(order) == 300 and order[0] == "A-001" and order[-1] == "M-010"
