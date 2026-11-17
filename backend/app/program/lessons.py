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
    """대분류(A→M)와 대분류 안 순서대로 레슨 id. 교육 자료 화면의 묶음 순서."""
    return sorted(_all(), key=lambda i: (i.split("-")[0], _all()[i][0]["order"], i))


@cache
def teaching_order() -> list[str]:
    """주간 배정 순서: 대분류를 돌아가며 하나씩(A1, B1, …, M1, A2, B2, …). 대분류 안 순서는 그대로.
    모든 단계가 같은 주제 순서로 배우고 양만 다르게(사용자, 2026-11-17). A→M 순서대로 주면 주 3개 단계는
    금지목록(G)까지 약 40주, 주 15개 단계는 약 8주라 단계마다 배우는 내용까지 달라지던 문제(테스터 1)."""
    by_cat: dict[str, list[str]] = {}
    for lesson_id in curriculum():
        by_cat.setdefault(lesson_id.split("-")[0], []).append(lesson_id)
    queues = list(by_cat.values())
    out: list[str] = []
    for i in range(max(len(q) for q in queues)):
        out += [q[i] for q in queues if i < len(q)]
    return out


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
