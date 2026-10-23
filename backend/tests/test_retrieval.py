"""검색 동작 (D14).

검색 정확도: 레슨 300개 기준 평가셋 두 개로 recall@K(K = 서버가 AI에 넘기는 청크 수)를 잰다.
- retrieval_eval.yaml(튜닝셋 60문항): synonyms.yaml을 고칠 때 보는 셋. 2026-10-23 recall@6 1.000(recall@3 0.950).
- retrieval_heldout.yaml(15문항): 동의어를 고칠 때 보지 않고 마지막에 한 번 잰 셋. 2026-10-23 recall@6 0.867.
기준은 달성값보다 조금 낮게 둔다. hold-out 기준은 D14 수용 기준(0.8)과 같다.
"""

from pathlib import Path

import pytest
import yaml

from app.chat.retrieve import K, _index, get_document, retrieve, unreviewed

HERE = Path(__file__).parent
SETS = {name: yaml.safe_load((HERE / f"{name}.yaml").read_text(encoding="utf-8"))
        for name in ("retrieval_eval", "retrieval_heldout")}
MIN_RECALL = {"retrieval_eval": 0.95, "retrieval_heldout": 0.8}


def test_every_chunk_is_unreviewed_or_reviewed_explicitly():
    assert all(isinstance(c.reviewed, bool) for c in _index().chunks)


def test_irrelevant_query_returns_nothing():
    # 두 글자 조각 BM25라 "추천"처럼 레슨에 흔한 단어가 하나라도 겹치면 결과가 나온다(최고점 대비 컷만 있고 절대 하한은 없음).
    # 여기서는 겹치는 단어가 없는 질문만 본다.
    assert retrieve("날씨 어때") == []


def test_unreviewed_chunks_are_listed():
    assert len(unreviewed()) == len([c for c in _index().chunks if not c.reviewed])


def test_empty_library_returns_no_results():
    """교육 문서가 없을 때도 검색은 오류 없이 빈 결과를 낸다(AI는 "근거 없음" 안내)."""
    if not _index().chunks:
        assert retrieve("감기약 먹어도 돼?") == []


@pytest.mark.parametrize("name", list(SETS))
def test_expected_lessons_exist(name):
    """평가셋의 정답은 실제 레슨 id여야 한다(레슨 id가 바뀌면 평가셋도 같이 고친다)."""
    if not _index().chunks:
        pytest.skip("교육 레슨 없음")
    missing = [d for case in SETS[name] for d in case["expect"] if get_document(d) is None]
    assert not missing, missing


@pytest.mark.parametrize("name", list(SETS))
def test_recall_at_k(name):
    """상위 K개 청크의 doc_id에 정답 레슨이 하나라도 있으면 성공. 튜닝셋과 hold-out을 따로 본다 —
    hold-out이 기준 아래인데 튜닝셋만 통과하는 상태(동의어 과적합)를 허용하지 않기 위해서다."""
    if not _index().chunks:
        pytest.skip("교육 레슨 없음")
    cases = SETS[name]
    misses = [c["q"] for c in cases if not {x.doc_id for x in retrieve(c["q"], k=K)} & set(c["expect"])]
    recall = 1 - len(misses) / len(cases)
    assert recall >= MIN_RECALL[name], f"{name} recall@{K} = {recall:.3f} < {MIN_RECALL[name]}, 실패: {misses}"
