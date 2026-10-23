"""근거 검색 (D13). knowledge/education/lessons/<대분류>/*.md 를 H2 섹션 단위 청크로 나눠 BM25로 찾는다.

문서 형식: YAML frontmatter(doc_id, category, title, source, url, version, reviewed, quiz …) + 본문의 `## 섹션`(knowledge/education/README.md).
청크 id = "{doc_id}#s{n}" (n은 문서 안 섹션 순서, 1부터). URL 경로에 넣을 때는 '#'을 인코딩해야 한다.

토큰화: 한국어는 띄어쓰기·조사 변형이 많아 어절마다 문자 bigram을 쓰고, 영문·숫자는 단어 그대로 쓴다.
구어체 질문("프로틴 먹어도 돼?")과 공문서체("보충제") 사이는 backend/settings/synonyms.yaml로 잇는다.
"""

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import yaml
from rank_bm25 import BM25Okapi

from app.config import LESSONS, SETTINGS
from app.schemas import Chunk

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.S)


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for word in re.findall(r"[0-9a-z]+|[가-힣]+", text.lower()):
        if word[0].isascii():
            tokens.append(word)
        elif len(word) == 1:
            tokens.append(word)
        else:
            tokens += [word[i:i + 2] for i in range(len(word) - 1)]
    return tokens


def read_doc(path: Path) -> tuple[dict, str]:
    """(frontmatter, 본문)."""
    match = FRONTMATTER.match(path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError(f"frontmatter 없음: {path}")
    return yaml.safe_load(match.group(1)), match.group(2)


def parse(path: Path) -> list[Chunk]:
    meta, body = read_doc(path)
    sections = re.split(r"^## +(.+)$", body, flags=re.M)[1:]
    return [
        Chunk(id=f"{meta['doc_id']}#s{n}", doc_id=meta["doc_id"], source=meta["source"], title=meta["title"],
              section=heading.strip(), url=meta["url"], version=str(meta["version"]),
              text=body.strip(), reviewed=meta["reviewed"])
        for n, (heading, body) in enumerate(zip(sections[::2], sections[1::2]), start=1)
    ]


# 서버가 AI에 넘기는 청크 수이자 검색 평가(recall@K)의 K. 둘을 따로 두지 않는다.
K = 6
# 섹션 점수에 더하는 문서 점수의 비중(둘 다 질문별 최댓값으로 나눈 뒤 더한다).
# 2026-10-17 retrieval_eval(튜닝셋)에서 0.2~0.6이 비슷하게 좋아 가운데 값을 골랐다.
DOC_WEIGHT = 0.4


def _doc_paths() -> list[Path]:
    """교육 레슨 .md(knowledge/education/lessons/ 아래). 원본 자료(raw/)와 안내 README는 레슨이 아니다."""
    return sorted(LESSONS.rglob("*.md"))


@dataclass(frozen=True)
class Index:
    chunks: tuple[Chunk, ...]
    bm25: BM25Okapi | None  # 교육 문서가 하나도 없으면 None(검색 결과 없음)
    doc_ids: tuple[str, ...]
    doc_bm25: BM25Okapi | None
    synonyms: dict[str, list[str]]


@cache
def _index() -> Index:
    chunks = tuple(c for path in _doc_paths() for c in parse(path))
    synonyms_path = SETTINGS / "synonyms.yaml"
    synonyms = yaml.safe_load(synonyms_path.read_text(encoding="utf-8")) if synonyms_path.exists() else {}
    if not chunks:  # 교육 자료를 다시 모으는 중이면 검색은 빈 결과(AI는 "근거 없음" 안내)
        return Index((), None, (), None, synonyms or {})
    # 제목과 섹션명을 본문 앞에 붙여 짧은 섹션도 주제어로 찾히게 한다
    bm25 = BM25Okapi([tokenize(f"{c.title} {c.section} {c.section} {c.text}") for c in chunks])
    # 2단계의 문서 단계: 제목·한 줄 소개·섹션 제목들로 "이 질문이 어느 문서 주제인가"를 본다.
    # 문서가 늘면 비슷한 낱말이 든 다른 문서의 섹션이 끼어들기 쉬워서, 주제가 맞는 문서의 섹션을 앞으로 당긴다.
    docs = _documents()
    doc_bm25 = BM25Okapi([tokenize(" ".join([m["title"], m.get("summary", ""), *[c.section for c in cs]]))
                          for m, cs in docs.values()])
    return Index(chunks, bm25, tuple(docs), doc_bm25, synonyms or {})


def expand(query: str) -> str:
    """구어체 표현이 들어 있으면 공문서 용어를 덧붙인다."""
    extra = [term for key, terms in _index().synonyms.items() if key in query for term in terms]
    return " ".join([query, *extra])



# 질문에 흔히 붙는 말. 두 글자 조각 검색에서 이 말만 겹친 엉뚱한 레슨이 올라오지 않게 질문에서 뺀다
QUESTION_WORDS = re.compile(r"(먹어도|마셔도|써도|맞아도|발라도|해도|돼요?|되나요|될까요?|되는|괜찮아요?|괜찮나요|괜찮을까요?|알려줘|알려\s*주세요|뭐야|뭐예요|이야(?!기)|어떻게|있어요?|없어요?)")
# 가장 높은 점수의 이 비율보다 낮은 청크는 근거로 넣지 않는다(질문과 상관없는 조각으로 토큰을 쓰지 않게)
MIN_RELATIVE = 0.6


def retrieve(query: str, k: int = K) -> list[Chunk]:
    """상위 k개 청크. 점수 = 섹션 BM25 + DOC_WEIGHT × 문서 BM25(각각 최댓값으로 정규화).
    섹션 자체 점수가 0이거나 최고점의 MIN_RELATIVE배 미만인 청크는 내지 않는다."""
    index = _index()
    if index.bm25 is None:
        return []
    tokens = tokenize(expand(QUESTION_WORDS.sub(" ", query)))
    if not tokens:
        return []
    scores = index.bm25.get_scores(tokens)
    doc_scores = dict(zip(index.doc_ids, index.doc_bm25.get_scores(tokens)))
    top, doc_top = max(scores) or 1.0, max(doc_scores.values()) or 1.0
    final = [scores[i] / top + DOC_WEIGHT * doc_scores[c.doc_id] / doc_top for i, c in enumerate(index.chunks)]
    order = sorted(range(len(index.chunks)),
                   key=lambda i: (-round(float(final[i]), 6), i))
    best = float(final[order[0]]) if order else 0.0
    return [index.chunks[i] for i in order[:k] if scores[i] > 0 and final[i] >= MIN_RELATIVE * best]


@cache
def _documents() -> dict[str, tuple[dict, tuple[Chunk, ...]]]:
    """doc_id → (frontmatter, 섹션 청크들). 순서는 파일 경로순."""
    return {meta["doc_id"]: (meta, tuple(parse(path)))
            for path in _doc_paths() for meta in [read_doc(path)[0]]}



def get_document(doc_id: str) -> tuple[dict, tuple[Chunk, ...]] | None:
    """문서 하나의 frontmatter와 섹션 전체(청크 id = 섹션 앵커)."""
    return _documents().get(doc_id)


def unreviewed() -> list[str]:
    """§10 G2: 연구진 검토 전 청크 id."""
    return [c.id for c in _index().chunks if not c.reviewed]
