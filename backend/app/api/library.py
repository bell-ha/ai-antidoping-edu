"""교육 자료 열람(관리자): 레슨 300개 전체를 읽는 화면용.

AI가 근거로 쓰는 레슨을 같은 로더(app.chat.retrieve)로 읽는다 — 화면에서 읽는 내용과 AI가 인용하는 내용이 어긋나지 않게.
섹션 id(s1, s2 …)는 rag 청크 id(`{doc_id}#s{n}`)의 뒷부분이라, AI 답변의 출처 칩에서 같은 섹션으로 바로 간다.
문서를 고쳐 쓰면 섹션 번호가 바뀔 수 있으므로 화면은 링크를 저장하지 않고 매번 API에서 받는다.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.api.login import admin as current
from app.chat import retrieve as rag
from app.program import lessons
from app.schemas import LibraryDoc, LibraryDocSummary, LibrarySection, SessionInfo

router = APIRouter(prefix="/api")


def _doc(doc_id: str) -> LibraryDoc | None:
    found = rag.get_document(doc_id)
    if found is None:
        return None
    meta, chunks = found
    return LibraryDoc(doc_id=meta["doc_id"], title=meta["title"], source=meta["source"], url=meta["url"],
                      version=str(meta["version"]), category=meta["category"],
                      summary=meta.get("summary"), reviewed=meta["reviewed"], quiz=meta.get("quiz"),
                      sections=[LibrarySection(id=c.id.split("#", 1)[1], heading=c.section, text=c.text) for c in chunks])


@router.get("/library", response_model=list[LibraryDocSummary])
def library(who: SessionInfo = Depends(current)) -> list[LibraryDocSummary]:
    out = []
    for doc_id in lessons.curriculum():  # 선수에게 배정되는 순서(A→M)
        d = _doc(doc_id)
        out.append(LibraryDocSummary(**d.model_dump(exclude={"sections", "quiz"}), section_headings=[s.heading for s in d.sections],
                                     length=sum(len(s.text) for s in d.sections)))
    return out


@router.get("/library/{doc_id}", response_model=LibraryDoc)
def document(doc_id: str, who: SessionInfo = Depends(current)) -> LibraryDoc:
    doc = _doc(doc_id)
    if doc is None:
        raise HTTPException(404, "자료를 찾지 못했어요.")
    return doc
