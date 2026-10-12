"""교육 콘텐츠 카탈로그 (D5).

선수 개인 프로파일은 저장하지 않는다 — 입력할 때마다 app.profiling.compute가 계산한다(D25).
여기에는 content_id·태그를 화면 문구로 푸는 함수만 남는다(지도자 팀 요약은 2026-10-12 삭제).
"""

from functools import cache

import yaml

from app.config import ROOT
from app.schemas import ProfileTag, Recommendation


@cache
def _catalog() -> dict:
    return yaml.safe_load((ROOT / "knowledge/catalog.yaml").read_text(encoding="utf-8"))


def recommendation(content_id: str) -> Recommendation:
    return Recommendation(content_id=content_id, **_catalog()["contents"][content_id])


def tag_label(tag: ProfileTag) -> str:
    return _catalog()["tags"][tag]
