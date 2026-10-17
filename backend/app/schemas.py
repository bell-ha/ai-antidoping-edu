"""데이터 계약 (DESIGN-DECISIONS.md).

API 응답과 내부 모듈(drugs.check, chat.retrieve, model.adapter, program)이 모두 이 모델을 따른다.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# 선수 = 교육 시작하기·질문하기만, 관리자 = 선수 관리·단계 설정·기록 입력 (D37)
Role = Literal["athlete", "admin"]
# 연구진 RNN의 대회 분류(world/continent/nation/etc)에 맞춘 입력 범주. 토큰 매핑은 model.predict가 한다
CompetitionCategory = Literal["world", "continent", "other_international", "domestic"]


# ---------- 로그인 (D37: 가입 없음, 관리자가 코드를 발급) ----------

class LoginRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)


class SessionInfo(BaseModel):
    role: Role
    athlete_id: int | None = None  # role == "athlete"일 때만
    label: str  # 화면 표시용 이름


# ---------- 연구진 모델 결과 ----------

class ModelValue(BaseModel):
    target: Literal["total"] = "total"
    unit: Literal["kg"] = "kg"
    value: float | None


class ObservedValue(BaseModel):
    value: int | None


class ModelResult(BaseModel):
    """연구진 경기력 모델의 결과 모양(인계본 profile() 반환값). 플랫폼은 이 결과만 쓴다(D32, D35).
    관측 − 예측은 줄 세우기에만 쓴다(D37). 도핑 여부·확률이 아니다."""
    model_version: str
    source: Literal["researchers", "platform_temporary", "synthetic", "none"]
    prediction: ModelValue
    observed: ObservedValue
    residual_observed_minus_predicted: float | None
    history_count: int
    prediction_interval_kg: float | None = None  # 연구진은 구간을 주지 않음
    data_warnings: list[str] = []


# ---------- 경기 기록 (관리자 입력) ----------

class RecordInput(BaseModel):
    """대회 1회. 체급(계체 체중)과 합계는 서버가 도출한다."""
    date: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")  # "YYYY-MM"
    competition_category: CompetitionCategory
    body_weight: float = Field(ge=30, le=200)
    snatch: int = Field(ge=1, le=300)
    clean_jerk: int = Field(ge=1, le=300)

    @field_validator("date")
    @classmethod
    def _not_future(cls, v: str) -> str:
        if v > date.today().strftime("%Y-%m"):
            raise ValueError("아직 오지 않은 달의 기록은 입력할 수 없어요.")
        return v


class RecordRow(RecordInput):
    id: int
    weight_class: int
    total: int


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
    roles: list[str]  # 레슨 frontmatter 그대로(검색 정렬에는 쓰지 않음)
    text: str
    reviewed: bool


# ---------- AI 교육 (D15) ----------

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)
    # assistant 턴은 서버가 그 답을 줄 때 붙인 서명이 있어야 한다 — 클라이언트가 지어낸 "이전 답변"을 막는다 (D33)
    token: str | None = Field(default=None, max_length=64)


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
    token: str = ""  # 다음 요청에서 이 답을 대화 기록으로 보낼 때 함께 보내는 서명 (D33)


class LibrarySection(BaseModel):
    id: str  # "s1" … — rag 청크 id의 "#s{n}"과 같은 번호
    heading: str
    text: str


class LibraryDocSummary(BaseModel):
    """GET /api/library 목록 한 줄."""
    doc_id: str
    title: str
    source: Source
    url: str
    version: str
    roles: list[str]  # 레슨 frontmatter 그대로(검색 정렬에는 쓰지 않음)
    topic: str | None = None  # 교육 주제 묶음(문서 frontmatter의 topic)
    summary: str | None = None
    reviewed: bool
    section_headings: list[str]
    length: int  # 본문 글자 수


class LibraryDoc(BaseModel):
    """GET /api/library/{doc_id}: 문서 전체."""
    doc_id: str
    title: str
    source: Source
    url: str
    version: str
    roles: list[str]  # 레슨 frontmatter 그대로(검색 정렬에는 쓰지 않음)
    topic: str | None = None
    summary: str | None = None
    reviewed: bool
    sections: list[LibrarySection]


class Survey(BaseModel):
    url: str  # 가명 ID가 채워진 외부 설문 주소


# ---------- 교육 프로그램 (D37) ----------

class TierSetting(BaseModel):
    """단계 하나(1 = 가장 낮음)."""
    tier: int = Field(ge=1)
    lessons_per_week: int = Field(ge=0, le=50)
    quiz_probability: float = Field(ge=0, le=1)  # 하루 첫 접속 때 갑자기 퀴즈가 나올 확률
    quiz_questions: int = Field(ge=1, le=10)  # 한 번에 나오는 문항 수


class ProgramSettings(BaseModel):
    tiers: list[TierSetting] = Field(min_length=1, max_length=10)


class QuizQuestion(BaseModel):
    """정답은 보내지 않는다."""
    lesson_id: str
    question: str
    choices: list[str]


class QuizAnswer(BaseModel):
    lesson_id: str
    choice: int = Field(ge=1, le=4)


class QuizResult(BaseModel):
    lesson_id: str
    correct: bool
    answer: int
    explanation: str


class LessonCard(BaseModel):
    lesson_id: str
    title: str
    category: str
    completed: bool


class LessonView(BaseModel):
    lesson_id: str
    title: str
    category: str
    sections: list["LibrarySection"]
    quiz: QuizQuestion
    completed: bool


class AthleteHome(BaseModel):
    name: str
    week_start: str  # 이번 주 월요일
    lessons: list[LessonCard]  # 이번 주에 들을 것(지난주에 못 들은 것 포함) + 이번 주 완료
    completed_total: int
    lesson_total: int
    surprise_quiz: list[QuizQuestion]  # 비어 있으면 없음


class AthleteRow(BaseModel):
    """관리자 선수 목록 한 줄."""
    id: int
    number: str
    name: str
    birth_year: int
    weight_class: int | None
    tier: int | None
    rank: int | None
    residual: float | None
    records: int
    lessons_completed: int
    quiz_correct: int
    quiz_wrong: int
    questions: int
    last_visit: str | None


class QuizLog(BaseModel):
    lesson_id: str
    title: str
    context: Literal["lesson", "surprise"]
    choice: int
    correct: bool
    at: str


class ChatLog(BaseModel):
    question: str
    answer: str
    at: str


class LessonLog(BaseModel):
    lesson_id: str
    title: str
    week_start: str
    completed_at: str | None


class AthleteDetail(BaseModel):
    athlete: AthleteRow
    records: list[RecordRow]
    model_result: ModelResult | None
    lessons: list[LessonLog]
    quizzes: list[QuizLog]
    chats: list[ChatLog]


class AthleteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=30)
    birth_year: int = Field(ge=1940, le=date.today().year - 8)


class IssuedCode(BaseModel):
    """새로 만든 로그인 코드. 서버에는 해시만 남아서 이때 한 번만 보인다."""
    athlete_id: int
    number: str
    code: str


class Overview(BaseModel):
    athletes: list[AthleteRow]
    settings: ProgramSettings
    model_version: str
