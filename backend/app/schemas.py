"""데이터 계약 (DESIGN-DECISIONS.md).

analysis/export.py가 쓰는 JSON, substances.check(), rag.retrieve(), API 응답이 모두 이 모델을 따른다.
D7: 사람에게 붙는 평가 용어 금지(DESIGN.md 6절). D8: 순위 관련 필드 없음. D15: 프롬프트에는 태그·연령대·경기 수준만.
"""

from typing import Literal

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

Role = Literal["athlete", "coach", "support"]
Sport = Literal["weightlifting"]  # D22: 종목 추상화 계층은 만들지 않음
# 연구진 RNN의 대회 분류(world/continent/nation/etc)에 맞춘 입력 범주. 토큰 매핑은 profiling이 한다:
# world→world, continent→continent, other_international→nation(데이터상 국제 초청전), domestic→etc(학습 자료에 없음)
CompetitionCategory = Literal["world", "continent", "other_international", "domestic"]
PerformanceModel = Literal["rnn", "synthetic_trend", "none"]


# ---------- 세션 (D23) ----------

class SessionRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)


class SessionInfo(BaseModel):
    """코드 하나가 가리키는 대상. demo_codes.json / access_codes.json의 값."""
    role: Role
    athlete_id: str | None = None  # role == "athlete"일 때만
    label: str  # 화면 표시용 ("선수 A", "지도자")


class DemoPersona(BaseModel):
    """GET /api/demo/personas. DEMO_MODE=1일 때만."""
    code: str
    info: SessionInfo
    description: str


# ---------- 선수 프로파일 ----------
# 선수가 입력한 기록으로 profiling.compute()가 만든다(D25). 저장하지 않는다.

ProfileTag = Literal["rapid_improvement", "decline", "weight_change", "high_level", "baseline"]


class RecordPoint(BaseModel):
    date: str  # "YYYY-MM". 대회명은 저장하지 않음 (§10 재식별)
    competition_category: CompetitionCategory
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


class ResidualPoint(BaseModel):
    """대회별 관측 − 예측(kg). 인계 계약이 허용한 표시 항목. σ 단위 시계열은 점수판처럼 읽혀 쓰지 않는다 (D7)."""
    date: str
    observed: int
    predicted: float
    diff_kg: float


class Reason(BaseModel):
    """추천 이유 = 규칙 입력값 직접 표시 (D6). 예: "예측 대비 +2.6σ (기준 2.0σ)" """
    tag: ProfileTag
    text: str


class RuleCheck(BaseModel):
    """판정 점검표 한 줄: 태그 규칙의 입력값·기준·충족 여부. 점수가 아니라 규칙 입력값 그대로(D6)."""
    tag: ProfileTag
    label: str  # 태그 표시명
    met: bool
    detail: str  # 예: "예측 대비 +1.5σ (기준 +2.0σ)", "이 성별은 예측 모델이 없어 판단하지 않음"


class Recommendation(BaseModel):
    """카탈로그 항목. content_id = knowledge/ 문서 ID → 추천 카드 → AI 교육 → 근거가 하나로 이어짐."""
    content_id: str
    title: str
    summary: str
    suggested_question: str


class AthleteProfile(BaseModel):
    """POST /api/profile/compute 결과. 선수 본인 세션에서만 만들어진다 (D9, D25)."""
    athlete_id: str
    sport: Sport
    sex: Literal["M", "F"]
    age: int  # 마지막 대회 연도 − 출생연도
    weight_class: int
    competition_category: CompetitionCategory  # 마지막 행
    model: PerformanceModel = "synthetic_trend"  # none이면 forecast·경기력 태그 없음(해당 성별 모델 없음)
    notices: list[str] = []  # 화면에 그대로 보여줄 상태 안내(예: "이 성별의 경기력 모델이 아직 없어요")
    records: list[RecordPoint]
    forecast: list[ForecastPoint]
    tags: list[ProfileTag]
    tag_labels: list[str] = []  # tags와 같은 순서. 표시명 출처는 knowledge/catalog.yaml 하나
    reasons: list[Reason]
    checks: list[RuleCheck] = []  # 붙지 않은 태그까지 모든 규칙의 판정 근거(테스트·설명용)
    recommendations: list[Recommendation]
    residuals: list[ResidualPoint] = []  # 대회별 관측 − 예측(kg)


# ---------- 직접 입력 (D25) ----------

class RecordInput(BaseModel):
    """선수가 입력하는 대회 1회. 체급(성별+계체 체중)과 합계는 서버가 도출한다."""
    date: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")  # "YYYY-MM"
    competition_category: CompetitionCategory
    body_weight: float = Field(ge=30, le=200)
    snatch: int = Field(ge=1, le=300)
    clean_jerk: int = Field(ge=1, le=300)


class ComputeRequest(BaseModel):
    """POST /api/profile/compute. 입력은 서버에 저장하지 않는다."""
    sex: Literal["M", "F"]
    birth_year: int = Field(ge=1940)  # 기록별 나이(모델 입력) 계산용. 저장하지 않는다
    records: list[RecordInput] = Field(min_length=3, max_length=10)
    confirmed: bool = False  # 경고를 사용자가 확인했는지

    @model_validator(mode="after")
    def _dates(self) -> "ComputeRequest":
        dates = [r.date for r in self.records]
        if dates != sorted(dates):
            raise ValueError("대회 기록은 오래된 것부터 날짜순으로 입력해 주세요.")
        if dates[-1] > date.today().strftime("%Y-%m"):
            raise ValueError("아직 오지 않은 달의 기록은 입력할 수 없어요.")
        age_first = int(dates[0][:4]) - self.birth_year
        if age_first < 8 or self.birth_year > date.today().year - 8:
            raise ValueError("출생연도와 대회 날짜를 다시 확인해 주세요.")
        return self


class PromptProfile(BaseModel):
    """세션에 저장하고 프롬프트에 넣는 것만 (D15, D25). 원 기록은 넣지 않는다."""
    tags: list[ProfileTag]
    age_band: str
    competition_category: CompetitionCategory


class InputWarning(BaseModel):
    row: int | None = None  # records 인덱스
    field: str | None = None
    code: Literal["ratio", "jump"]
    message: str


class DemoScenario(BaseModel):
    """DEMO_MODE 테스트 시나리오 목록 한 줄. expect는 지금 서버의 예측 방식 기준 기대 태그."""
    id: str
    label: str
    description: str
    sex: Literal["M", "F"]
    expect: list[ProfileTag]
    expect_labels: list[str]
    warnings: list[Literal["ratio", "jump"]] = []


class DemoScenarios(BaseModel):
    model: Literal["synthetic_trend", "rnn"]  # 이 서버가 쓰는 예측 방식(params의 model)
    scenarios: list[DemoScenario]


class ComputeResponse(BaseModel):
    profile: AthleteProfile | None  # 경고가 있고 confirmed=false면 None
    warnings: list[InputWarning]


# ---------- 약물 확인 (D10, D11, D12) ----------

Timing = Literal["in_competition", "out_of_competition", "unknown"]
CheckStatus = Literal["PROHIBITED", "IN_COMPETITION_ONLY", "THRESHOLD", "CONDITIONAL", "NOT_LISTED_VERIFY", "UNKNOWN"]
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


class DataSource(BaseModel):
    """판정에 쓴 공공데이터 출처 표시(예: 공공누리 제1유형은 출처 표시가 조건)."""
    label: str
    url: str


class ProductCandidate(BaseModel):
    """같은 이름의 제품이 여럿이고 성분 구성이 다를 때의 후보(판정하지 않음)."""
    name: str
    otc: str  # 전문 / 일반
    ingredients: list[str]  # 영문 성분명


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
    data_sources: list[DataSource] = []
    candidates: list[ProductCandidate] = []  # 최대 10개


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
