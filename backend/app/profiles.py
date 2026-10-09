"""교육 콘텐츠 카탈로그와 데모 팀 요약 (D5, D9).

선수 개인 프로파일은 저장하지 않는다 — 입력할 때마다 app.profiling.compute가 계산한다(D25).
여기에는 content_id·태그를 화면 문구로 푸는 함수와, DEMO_MODE의 지도자 팀 요약만 남는다.
"""

import json
from functools import cache

import yaml

from app.config import DATA, ROOT
from app.schemas import ProfileTag, Recommendation, TeamSummary, TeamSummaryRecord


@cache
def _catalog() -> dict:
    return yaml.safe_load((ROOT / "knowledge/catalog.yaml").read_text(encoding="utf-8"))


@cache
def _teams() -> dict[str, TeamSummaryRecord]:
    rows = json.loads((DATA / "team_summary.json").read_text(encoding="utf-8"))
    return {r["team_id"]: TeamSummaryRecord.model_validate(r) for r in rows}


def recommendation(content_id: str) -> Recommendation:
    return Recommendation(content_id=content_id, **_catalog()["contents"][content_id])


def tag_label(tag: ProfileTag) -> str:
    return _catalog()["tags"][tag]


def load_team_summary(team_id: str) -> TeamSummary | None:
    record = _teams().get(team_id)
    if record is None:
        return None
    return TeamSummary(team_id=team_id, topics=[recommendation(c) for c in record.topics])
