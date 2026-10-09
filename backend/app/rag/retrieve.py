"""근거 검색 (D13). knowledge/<출처>/*.md 를 H2 섹션 단위 청크로 나눠 BM25로 찾는다.

문서 형식: YAML frontmatter(doc_id, source, title, url, version, roles, reviewed) + 본문의 `## 섹션`.
청크 id = "{doc_id}#s{n}" (n은 문서 안 섹션 순서, 1부터). URL 경로에 넣을 때는 '#'을 인코딩해야 한다.

토큰화: 한국어는 띄어쓰기·조사 변형이 많아 어절마다 문자 bigram을 쓰고, 영문·숫자는 단어 그대로 쓴다.
구어체 질문("프로틴 먹어도 돼?")과 공문서체("보충제") 사이는 knowledge/synonyms.yaml로 잇는다.
"""

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import yaml
from rank_bm25 import BM25Okapi

from app.config import ROOT
from app.schemas import Chunk, Role

KNOWLEDGE = ROOT / "knowledge"
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


def parse(path: Path) -> list[Chunk]:
    match = FRONTMATTER.match(path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError(f"frontmatter 없음: {path}")
    meta = yaml.safe_load(match.group(1))
    sections = re.split(r"^## +(.+)$", match.group(2), flags=re.M)[1:]
    return [
        Chunk(id=f"{meta['doc_id']}#s{n}", doc_id=meta["doc_id"], source=meta["source"], title=meta["title"],
              section=heading.strip(), url=meta["url"], version=str(meta["version"]), roles=meta["roles"],
              text=body.strip(), reviewed=meta["reviewed"])
        for n, (heading, body) in enumerate(zip(sections[::2], sections[1::2]), start=1)
    ]


@dataclass(frozen=True)
class Index:
    chunks: tuple[Chunk, ...]
    bm25: BM25Okapi
    synonyms: dict[str, list[str]]


@cache
def _index() -> Index:
    chunks = tuple(c for path in sorted(KNOWLEDGE.glob("*/*.md")) for c in parse(path))
    if not chunks:
        raise RuntimeError("knowledge/ 코퍼스가 비어 있음")
    # 제목과 섹션명을 본문 앞에 붙여 짧은 섹션도 주제어로 찾히게 한다
    bm25 = BM25Okapi([tokenize(f"{c.title} {c.section} {c.section} {c.text}") for c in chunks])
    synonyms_path = KNOWLEDGE / "synonyms.yaml"
    synonyms = yaml.safe_load(synonyms_path.read_text(encoding="utf-8")) if synonyms_path.exists() else {}
    return Index(chunks, bm25, synonyms or {})


def expand(query: str) -> str:
    """구어체 표현이 들어 있으면 공문서 용어를 덧붙인다."""
    extra = [term for key, terms in _index().synonyms.items() if key in query for term in terms]
    return " ".join([query, *extra])


def get_chunk(chunk_id: str) -> Chunk | None:
    """출처 팝오버용 (/api/sources/{chunk_id})."""
    return next((c for c in _index().chunks if c.id == chunk_id), None)


def retrieve(query: str, k: int = 4, role: Role | None = None) -> list[Chunk]:
    """상위 k개 청크. role은 점수가 같을 때 역할이 맞는 청크를 앞에 두는 데만 쓴다. 점수 0인 청크는 내지 않는다."""
    index = _index()
    scores = index.bm25.get_scores(tokenize(expand(query)))
    order = sorted(range(len(index.chunks)),
                   key=lambda i: (-round(float(scores[i]), 6), role is not None and role not in index.chunks[i].roles, i))
    return [index.chunks[i] for i in order[:k] if scores[i] > 0]


def unreviewed() -> list[str]:
    """§10 G2: 연구진 검토 전 청크 id."""
    return [c.id for c in _index().chunks if not c.reviewed]
