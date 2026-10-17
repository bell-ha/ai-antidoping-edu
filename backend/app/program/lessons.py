"""레슨 300개 읽기 (knowledge/education/lessons, 형식은 knowledge/education/README.md).

순서는 대분류 글자(A→M) 다음 frontmatter의 order — ADEL 국제 선수 과정의 모듈 순서를 따른 대분류 순서다.
레슨 파일은 AI 검색(chat.retrieve)과 같은 로더로 읽는다: 선수가 읽는 내용과 AI가 인용하는 내용이 같다.
"""

from functools import cache

from app import config
from app.chat.retrieve import parse, read_doc
from app.schemas import LibrarySection, QuizQuestion, QuizResult


@cache
def _all() -> dict[str, tuple[dict, list[LibrarySection]]]:
    out = {}
    for path in sorted(config.LESSONS.rglob("*.md")):
        meta, _ = read_doc(path)
        sections = [LibrarySection(id=c.id.split("#", 1)[1], heading=c.section, text=c.text) for c in parse(path)]
        out[meta["doc_id"]] = (meta, sections)
    return out


@cache
def curriculum() -> list[str]:
    """배정 순서대로 레슨 id."""
    return sorted(_all(), key=lambda i: (i.split("-")[0], _all()[i][0]["order"], i))


def exists(lesson_id: str) -> bool:
    return lesson_id in _all()


def meta(lesson_id: str) -> dict:
    return _all()[lesson_id][0]


def sections(lesson_id: str) -> list[LibrarySection]:
    return _all()[lesson_id][1]


def title(lesson_id: str) -> str:
    return meta(lesson_id)["title"] if exists(lesson_id) else lesson_id


def question(lesson_id: str) -> QuizQuestion:
    q = meta(lesson_id)["quiz"]
    return QuizQuestion(lesson_id=lesson_id, question=q["question"], choices=q["choices"])


def grade(lesson_id: str, choice: int) -> QuizResult:
    q = meta(lesson_id)["quiz"]
    return QuizResult(lesson_id=lesson_id, correct=choice == q["answer"], answer=q["answer"], explanation=q["explanation"])
