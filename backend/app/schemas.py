"""데이터 계약 (DESIGN-DECISIONS.md).

analysis/export.py가 쓰는 JSON, substances.check(), rag.retrieve(), API 응답이 모두 이 모델을 따른다.
D7: 사람에게 붙는 평가 용어 금지(DESIGN.md 6절). D8: 순위 관련 필드 없음. D15: 프롬프트에는 태그·연령대·경기 수준만.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["athlete", "coach", "support"]
Sport = Literal["weightlifting"]  # D22: 종목 추상화 계층은 만들지 않음
CompetitionLevel = Literal["junior", "national", "international"]


# ---------- 세션 (D23) ----------

class SessionRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)


class SessionInfo(BaseModel):
    """코드 하나가 가리키는 대상. demo_codes.json / access_codes.json의 값."""
    role: Role
    athlete_id: str | None = None  # role == "athlete"일 때만
    team_id: str | None = None
    label: str  # 화면 표시용 ("선수 A", "지도자")


class DemoPersona(BaseModel):
    """GET /api/demo/personas. DEMO_MODE=1일 때만."""
    code: str
    info: SessionInfo
    description: str


# ---------- 선수 프로파일 ----------
# 저장 형태(ProfileRecord, data/profiles.json)는 analysis/export.py가 쓰고,
# API 형태(AthleteProfile)는 profiles.py가 content_id를 카탈로그로 풀어서 만든다.

ProfileTag = Literal["rapid_improvement", "decline", "weight_change", "high_level", "baseline"]


class RecordPoint(BaseModel):
    date: str  # "YYYY-MM". 대회명은 저장하지 않음 (§10 재식별)
    competition_level: CompetitionLevel
    weight_class: int  # 2018 IWF 체급 (D22)
    body_weight: float
    snatch: int
    clean_jerk: int
    total: int


class ForecastPoint(BaseModel):
    date: str
    mean: float
    lo: float  # 체급별 잔차 σ × 1.96 (D4)
    hi: float


class Reason(BaseModel):
    """추천 이유 = 규칙 입력값 직접 표시 (D6). 예: "예측 대비 +2.6σ (기준 2.0σ)" """
    tag: ProfileTag
    text: str


class ProfileRecord(BaseModel):
    """data/profiles.json의 한 항목. 순위 관련 값은 넣지 않음 (D8을 구조로 보장)."""
    athlete_id: str
    sport: Sport = "weightlifting"
    sex: Literal["M", "F"]
    age: int  # birth_year 대신 (§10)
    age_band: str  # 프롬프트에는 이것만 (D15)
    weight_class: int
    competition_level: CompetitionLevel
    records: list[RecordPoint]
    forecast: list[ForecastPoint]
    tags: list[ProfileTag]
    reasons: list[Reason]
    recommendations: list[str]  # content_id, 순서는 export가 정함


class TeamSummaryRecord(BaseModel):
    """data/team_summary.json. 카탈로그 고정 순서, 인원수 없음 (D9)."""
    team_id: str
    topics: list[str]  # content_id


class Recommendation(BaseModel):
    """카탈로그 항목. content_id = knowledge/ 문서 ID → 추천 카드 → AI 교육 → 근거가 하나로 이어짐."""
    content_id: str
    title: str
    summary: str
    suggested_question: str


class AthleteProfile(BaseModel):
    """GET /api/me. 본인 세션으로만 조회 (D9, D23)."""
    athlete_id: str
    sport: Sport
    sex: Literal["M", "F"]
    age: int
    weight_class: int
    competition_level: CompetitionLevel
    records: list[RecordPoint]
    forecast: list[ForecastPoint]
    tags: list[ProfileTag]
    tag_labels: list[str] = []  # tags와 같은 순서. 표시명 출처는 knowledge/catalog.yaml 하나
    reasons: list[Reason]
    recommendations: list[Recommendation]


class TeamSummary(BaseModel):
    """GET /api/team/summary."""
    team_id: str
    topics: list[Recommendation]


# ---------- 약물 확인 (D10, D11, D12) ----------

Timing = Literal["in_competition", "out_of_competition", "unknown"]
CheckStatus = Literal["PROHIBITED", "IN_COMPETITION_ONLY", "THRESHOLD", "NOT_LISTED_VERIFY", "UNKNOWN"]
CountryRoute = Literal["kada", "globaldro", "local_unverified"]


class CheckRequest(BaseModel):
    query: str = Field(min_length=1, max_length=100)
    country: str = Field(min_length=2, max_length=2)  # ISO 3166-1 alpha-2
    timing: Timing


class Ingredient(BaseModel):
    name_ko: str
    name_en: str
    status: CheckStatus
    wada_class: str | None = None  # "S6" 등
    note: str | None = None  # 기준치 설명 등
    source_url: str


class OfficialLink(BaseModel):
    label: str
    url: str


class CheckResult(BaseModel):
    query: str
    matched_kind: Literal["product", "category", "substance", "unmatched"]
    status: CheckStatus  # category·unmatched면 항상 UNKNOWN. "허용" 상태 없음
    ingredients: list[Ingredient]  # category면 "주의 성분"
    timing: Timing
    country: str
    route: CountryRoute
    steps: list[str]
    links: list[OfficialLink]  # 항상 하나 이상
    supplement_warning: bool
    related_chunk_ids: list[str] = []
    list_version: str  # "2026"
    reviewed: bool


# ---------- RAG (D13) ----------

Source = Literal["WADA", "KADA", "ADEL", "GlobalDRO"]


class Chunk(BaseModel):
    id: str  # "{doc_id}#{section-slug}"
    doc_id: str
    source: Source
    title: str
    section: str
    url: str
    version: str
    roles: list[Role]
    text: str
    reviewed: bool


# ---------- AI 교육 (D15) ----------

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class ChatContext(BaseModel):
    check_result: CheckResult | None = None  # "AI에게 더 묻기"
    content_id: str | None = None  # 추천 카드에서 진입


class ChatRequest(BaseModel):
    """role·athlete_id는 세션에서만 (D23). 본문에 넣어도 무시된다."""
    model_config = ConfigDict(extra="ignore")
    messages: list[ChatMessage] = Field(min_length=1, max_length=20)
    context: ChatContext | None = None


class LlmAnswer(BaseModel):
    """LLM 구조화 출력. citations는 프롬프트에 넣은 chunk_id만 허용 (guard가 검증)."""
    answer: str
    citations: list[str]
    refer_to_expert: bool
    out_of_scope: bool


class Citation(BaseModel):
    chunk_id: str
    source: Source
    title: str
    url: str


class ChatResponse(BaseModel):
    kind: Literal["answer", "fixed", "server"] = "answer"  # fixed = 회피·강요 고정 응답, server = 근거 없음·오류 등 서버 문구
    answer: str
    citations: list[Citation]
    refer_to_expert: bool  # LLM 판단 OR 서버 규칙
    out_of_scope: bool
