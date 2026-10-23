"""데이터 계약.

API 응답과 내부 모듈(drugs.check, chat.retrieve, model.adapter, program)이 모두 이 모델을 따른다.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# 선수 = 교육 시작하기·질문하기만, 관리자 = 선수 관리·단계 설정·기록 입력
Role = Literal["athlete", "admin"]
# 연구진 RNN의 대회 분류(world/continent/nation/etc)에 맞춘 입력 범주. 토큰 매핑은 model.predict가 한다
CompetitionCategory = Literal["world", "continent", "other_international", "domestic"]


# ---------- 로그인 (가입 없음, 관리자가 코드를 발급) ----------

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
    """연구진 경기력 모델의 결과 모양(인계본 profile() 반환값). 플랫폼은 이 결과만 쓴다.
    관측 − 예측은 줄 세우기에만 쓴다. 도핑 여부·확률이 아니다."""
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
        from app.db import now  # 한국 시간 기준(서버가 UTC로 돌아도 매달 1일 아침에 이번 달이 막히지 않게)
        if v > now().strftime("%Y-%m"):
            raise ValueError("아직 오지 않은 달의 기록은 입력할 수 없어요.")
        return v


class RecordRow(RecordInput):
    id: int
    weight_class: int
    total: int


# ---------- 약물 확인 ----------

Timing = Literal["in_competition", "out_of_competition", "unknown"]
CheckStatus = Literal["PROHIBITED", "IN_COMPETITION_ONLY", "THRESHOLD", "CONDITIONAL", "NOT_LISTED_VERIFY", "UNKNOWN"]
CountryRoute = Literal["kada", "local_unverified"]


class Ingredient(BaseModel):
    name_ko: str
    name_en: str
    status: CheckStatus
    wada_class: str | None = None  # "S6.B" 등
    wada_class_ko: str | None = None  # "특정 흥분제" — KADA 국문판 분류 이름(kada/processed)
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
    status: CheckStatus | None = None  # 이 제품의 성분 판정 중 가장 엄격한 것(성분 정보가 없으면 None)


class CheckResult(BaseModel):
    query: str
    matched_kind: Literal["product", "category", "substance", "unmatched"]
    status: CheckStatus  # category·unmatched면 항상 UNKNOWN. "허용" 상태 없음
    ingredients: list[Ingredient]  # category면 "주의 성분"
    timing: Timing
    country: str
    route: CountryRoute
    note: str | None = None  # 조회표 항목의 설명(한약재 출처, 보충제 안내 등)
    steps: list[str]
    links: list[OfficialLink]  # 항상 하나 이상
    supplement_warning: bool
    related_chunk_ids: list[str] = []
    list_version: str  # "2026"
    reviewed: bool
    data_sources: list[DataSource] = []
    candidates: list[ProductCandidate] = []  # 최대 10개


# ---------- RAG ----------

Source = Literal["WADA", "KADA", "ADEL"]


class Chunk(BaseModel):
    id: str  # "{doc_id}#{section-slug}"
    doc_id: str
    source: Source
    title: str
    section: str
    url: str
    version: str
    text: str
    reviewed: bool


# ---------- 질문하기 ----------

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)
    # assistant 턴은 서버가 그 답을 줄 때 붙인 서명이 있어야 한다 — 클라이언트가 지어낸 "이전 답변"을 막는다
    token: str | None = Field(default=None, max_length=64)


class ChatRequest(BaseModel):
    """누가 묻는지는 세션에서만 안다. 본문에 다른 필드를 넣어도 무시된다.
    서버는 마지막 질문과 그 앞 대화 2번(api.chat.HISTORY_TURNS)만 AI에 보낸다."""
    model_config = ConfigDict(extra="ignore")
    messages: list[ChatMessage] = Field(min_length=1, max_length=20)


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
    token: str = ""  # 다음 요청에서 이 답을 대화 기록으로 보낼 때 함께 보내는 서명
    drug_checks: list["CheckResult"] = []  # 질문 속 약 이름의 조회표 판정(AI 설명과 함께 화면에 카드로)
    related_lessons: list["RelatedLesson"] = []  # 답에 인용된 레슨 = 더 읽어 볼 교육


class RelatedLesson(BaseModel):
    lesson_id: str
    title: str
    category: str


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
    category: str  # 대분류("G 금지목록") — 선수 화면과 같은 묶음
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
    category: str
    summary: str | None = None
    reviewed: bool
    sections: list[LibrarySection]


class Survey(BaseModel):
    url: str  # 가명 ID가 채워진 외부 설문 주소


# ---------- 교육 프로그램 ----------

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
    wrong_open: int  # 마지막으로 푼 답이 오답인 교육 수(오답 노트에 남은 것)
    questions: int
    last_visit: str | None


class QuizLog(BaseModel):
    lesson_id: str
    title: str
    context: Literal["lesson", "surprise", "review"]
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


class HistoryItem(BaseModel):
    """내 학습 기록 한 줄: 이수한 교육과 그 퀴즈를 마지막으로 풀었을 때 결과."""
    lesson_id: str
    title: str
    category: str
    completed_at: str
    attempts: int
    last_correct: bool | None


class AthleteHistory(BaseModel):
    completed: int
    lesson_total: int
    quiz_correct: int
    quiz_wrong: int
    items: list[HistoryItem]  # 이수한 순서
    wrong: list[QuizQuestion]  # 오답 다시 풀기: 마지막 답이 오답인 교육


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

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("이름을 입력해 주세요.")
        return v.strip()


class IssuedCode(BaseModel):
    """새로 만든 로그인 코드. 서버에는 해시만 남아서 이때 한 번만 보인다."""
    athlete_id: int
    number: str
    code: str


class Overview(BaseModel):
    athletes: list[AthleteRow]
    settings: ProgramSettings
    model_version: str


class DemoCode(BaseModel):
    """로그인 화면 오른쪽 데모 코드 목록(DEMO_MODE=1일 때만)."""
    number: str
    name: str
    role: Role
    code: str
    tier: int | None = None
