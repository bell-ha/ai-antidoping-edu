"""검색 동작 (D14).

검색 정확도 평가셋(튜닝셋·hold-out)은 교육 문서를 새로 모은 뒤 다시 만든다 — 2026-10-17 문서 22개를 지우면서
그 문서의 섹션을 기대값으로 가진 평가셋도 함께 뺐다(기록: DESIGN-DECISIONS D14).
"""

from app.chat.retrieve import retrieve, unreviewed
from app.chat.retrieve import _index


def test_every_chunk_is_unreviewed_or_reviewed_explicitly():
    assert all(isinstance(c.reviewed, bool) for c in _index().chunks)


def test_irrelevant_query_returns_nothing():
    # 두 글자 조각 BM25라 "추천"처럼 레슨에 흔한 단어가 하나라도 겹치면 결과가 나온다(관련도 하한 없음).
    # 하한은 레슨 300개 기준 평가셋을 다시 만든 뒤 정한다. 여기서는 겹치는 단어가 없는 질문만 본다.
    assert retrieve("날씨 어때") == []


def test_unreviewed_chunks_are_listed():
    assert len(unreviewed()) == len([c for c in _index().chunks if not c.reviewed])


def test_empty_library_returns_no_results():
    """교육 문서가 없을 때도 검색은 오류 없이 빈 결과를 낸다(AI는 "근거 없음" 안내)."""
    if not _index().chunks:
        assert retrieve("감기약 먹어도 돼?") == []
