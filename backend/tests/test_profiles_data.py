"""analysis/export.py 생성물 계약 테스트 (D7, D8, D9)."""

import json

from app.config import DATA
from app.profiles import load_profile, load_team_summary
from app.schemas import ProfileRecord, TeamSummaryRecord

PROFILES = json.loads((DATA / "profiles.json").read_text(encoding="utf-8"))
TEAMS = json.loads((DATA / "team_summary.json").read_text(encoding="utf-8"))


def test_files_match_schema():
    for p in PROFILES:
        ProfileRecord.model_validate(p)
    for t in TEAMS:
        TeamSummaryRecord.model_validate(t)


def test_one_signal_per_persona():
    """§2: 페르소나 하나에 표의 행 하나."""
    assert {p["athlete_id"]: p["tags"] for p in PROFILES} == {
        "A": ["rapid_improvement"], "B": ["decline"], "C": ["weight_change"], "D": ["high_level"], "E": ["baseline"]}


def test_no_percentile_or_rank_anywhere():
    """D8: 백분위는 추천 순서에만 쓰고 어떤 출력에도 남기지 않는다."""
    raw = (DATA / "profiles.json").read_text(encoding="utf-8")
    for word in ("percentile", "백분위", "상위", "순위", "rank"):
        assert word not in raw


def test_no_birth_year_in_served_data():
    """§10: 서버 JSON에는 birth_year 대신 age."""
    assert all("birth_year" not in p for p in PROFILES)


def test_team_summary_has_topics_only():
    """D9: 이름·인원수 없음."""
    for t in TEAMS:
        assert set(t) == {"team_id", "topics"}
        assert all(isinstance(c, str) for c in t["topics"])


def test_api_shapes_resolve_catalog():
    a = load_profile("A")
    assert a.tag_labels == ["최근 경기력 급격한 향상"]
    assert a.recommendations[0].suggested_question
    assert load_team_summary("demo-team").topics
