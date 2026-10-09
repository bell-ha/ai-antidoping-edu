"""교육 프로파일 조회 (D5, D9). analysis/export.py가 만든 JSON을 읽기만 한다.

저장 형태(ProfileRecord)의 content_id를 knowledge/catalog.yaml로 풀어 API 형태로 바꾼다.
호출하는 쪽은 athlete_id·team_id를 반드시 세션에서 꺼내 넘겨야 한다(D23).
"""

import json
from functools import cache
from pathlib import Path

import yaml

from app.schemas import AthleteProfile, ProfileRecord, ProfileTag, Recommendation, TeamSummary, TeamSummaryRecord

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
KNOWLEDGE = ROOT / "knowledge"


@cache
def _catalog() -> dict:
    return yaml.safe_load((KNOWLEDGE / "catalog.yaml").read_text(encoding="utf-8"))


@cache
def _profiles() -> dict[str, ProfileRecord]:
    rows = json.loads((DATA / "profiles.json").read_text(encoding="utf-8"))
    return {r["athlete_id"]: ProfileRecord.model_validate(r) for r in rows}


@cache
def _teams() -> dict[str, TeamSummaryRecord]:
    rows = json.loads((DATA / "team_summary.json").read_text(encoding="utf-8"))
    return {r["team_id"]: TeamSummaryRecord.model_validate(r) for r in rows}


def recommendation(content_id: str) -> Recommendation:
    return Recommendation(content_id=content_id, **_catalog()["contents"][content_id])


def tag_label(tag: ProfileTag) -> str:
    return _catalog()["tags"][tag]


def load_profile(athlete_id: str) -> AthleteProfile | None:
    record = _profiles().get(athlete_id)
    if record is None:
        return None
    data = record.model_dump(exclude={"age_band", "recommendations"})
    return AthleteProfile(**data, tag_labels=[tag_label(t) for t in record.tags],
                          recommendations=[recommendation(c) for c in record.recommendations])


def load_record(athlete_id: str) -> ProfileRecord | None:
    """프롬프트용. 호출 쪽은 tags·age_band·competition_level만 써야 한다(D15)."""
    return _profiles().get(athlete_id)


def load_team_summary(team_id: str) -> TeamSummary | None:
    record = _teams().get(team_id)
    if record is None:
        return None
    return TeamSummary(team_id=team_id, topics=[recommendation(c) for c in record.topics])
