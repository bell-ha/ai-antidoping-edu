"""검색 수용 기준 (D14): retrieval_eval.yaml에서 recall@4 >= 0.8."""

from pathlib import Path

import yaml

from app.rag import get_chunk, retrieve
from app.rag.retrieve import _index

import pytest

HERE = Path(__file__).parent
SETS = {name: yaml.safe_load((HERE / f"{name}.yaml").read_text(encoding="utf-8"))
        for name in ("retrieval_eval", "retrieval_heldout")}


def test_expected_chunks_exist():
    for case in [c for cases in SETS.values() for c in cases]:
        for chunk_id in case["expect"]:
            assert get_chunk(chunk_id) is not None, chunk_id


@pytest.mark.parametrize("name", list(SETS))
def test_recall_at_4(name):
    """튜닝셋(retrieval_eval)과 독립 hold-out 모두 0.8 이상. hold-out이 떨어지면 실패로 본다 —
    독립 수치가 기준을 못 넘는데 튜닝셋만 통과하는 상태를 허용하지 않기 위해서다."""
    cases = SETS[name]
    misses = [c["q"] for c in cases if not {x.id for x in retrieve(c["q"], k=4)} & set(c["expect"])]
    recall = 1 - len(misses) / len(cases)
    assert recall >= 0.8, f"{name} recall@4 = {recall:.2f}, 실패: {misses}"


def test_catalog_contents_have_documents():
    """추천 카드 → AI 교육 → 근거가 하나로 이어지려면 catalog의 content_id마다 문서가 있어야 한다."""
    catalog = yaml.safe_load((Path(__file__).parents[2] / "knowledge/catalog.yaml").read_text(encoding="utf-8"))
    docs = {c.doc_id for c in _index().chunks}
    assert set(catalog["contents"]) <= docs


def test_every_chunk_is_unreviewed_or_reviewed_explicitly():
    assert all(isinstance(c.reviewed, bool) for c in _index().chunks)


def test_irrelevant_query_returns_nothing():
    assert retrieve("오늘 점심 메뉴 추천해줘") == []


def test_unreviewed_chunks_are_listed():
    from app.rag import unreviewed
    assert len(unreviewed()) == len(_index().chunks)
