// backend/app/schemas.py와 같은 모양. 바꾸면 양쪽을 같이 고친다.

export type Role = "athlete" | "admin";
export type CheckStatus = "PROHIBITED" | "IN_COMPETITION_ONLY" | "THRESHOLD" | "CONDITIONAL" | "NOT_LISTED_VERIFY" | "UNKNOWN";
export type Timing = "in_competition" | "out_of_competition" | "unknown";
export type CompetitionCategory = "world" | "continent" | "other_international" | "domestic";

export interface SessionInfo {
  role: Role;
  athlete_id: number | null;
  label: string;
}

export interface DemoCode {
  number: string;
  name: string;
  role: Role;
  code: string;
  tier: number | null;
}

export interface ModelResult {
  model_version: string;
  source: "researchers" | "platform_temporary" | "synthetic" | "none";
  prediction: { target: "total"; unit: "kg"; value: number | null };
  observed: { value: number | null };
  residual_observed_minus_predicted: number | null;
  history_count: number;
  prediction_interval_kg: number | null;
  data_warnings: string[];
}

export interface RecordInput {
  date: string; // "YYYY-MM"
  competition_category: CompetitionCategory;
  body_weight: number;
  snatch: number;
  clean_jerk: number;
}

export interface RecordRow extends RecordInput {
  id: number;
  weight_class: number;
  total: number;
}

// ---------- 교육 프로그램 ----------

export interface TierSetting {
  tier: number;
  lessons_per_week: number;
  quiz_probability: number;
  quiz_questions: number;
}

export interface ProgramSettings {
  tiers: TierSetting[];
}

export interface QuizQuestion {
  lesson_id: string;
  question: string;
  choices: string[];
}

export interface QuizResult {
  lesson_id: string;
  correct: boolean;
  answer: number;
  explanation: string;
}

export interface LessonCard {
  lesson_id: string;
  title: string;
  category: string;
  completed: boolean;
}

export interface LessonView {
  lesson_id: string;
  title: string;
  category: string;
  sections: LibrarySection[];
  quiz: QuizQuestion;
  completed: boolean;
}

export interface AthleteHome {
  name: string;
  week_start: string;
  lessons: LessonCard[];
  completed_total: number;
  lesson_total: number;
  surprise_quiz: QuizQuestion[];
}

export interface AthleteRow {
  id: number;
  number: string;
  name: string;
  birth_year: number;
  weight_class: number | null;
  tier: number | null;
  rank: number | null;
  residual: number | null;
  records: number;
  lessons_completed: number;
  quiz_correct: number;
  quiz_wrong: number;
  wrong_open: number;
  questions: number;
  last_visit: string | null;
}

export interface AthleteDetail {
  athlete: AthleteRow;
  records: RecordRow[];
  model_result: ModelResult | null;
  lessons: { lesson_id: string; title: string; week_start: string; completed_at: string | null }[];
  quizzes: { lesson_id: string; title: string; context: "lesson" | "surprise" | "review"; choice: number; correct: boolean; at: string }[];
  chats: { question: string; answer: string; at: string }[];
}

export interface AthleteHistory {
  completed: number;
  lesson_total: number;
  quiz_correct: number;
  quiz_wrong: number;
  items: { lesson_id: string; title: string; category: string; completed_at: string; attempts: number; last_correct: boolean | null }[];
  wrong: QuizQuestion[];
}

export interface Overview {
  athletes: AthleteRow[];
  settings: ProgramSettings;
  model_version: string;
}

export interface IssuedCode {
  athlete_id: number;
  number: string;
  code: string;
}

export interface Ingredient {
  name_ko: string;
  name_en: string;
  status: CheckStatus;
  wada_class: string | null;
  wada_class_ko: string | null;
  note: string | null;
  source_url: string;
}

export interface CheckResult {
  query: string;
  matched_kind: "product" | "category" | "substance" | "unmatched";
  status: CheckStatus;
  ingredients: Ingredient[];
  timing: Timing;
  country: string;
  route: "kada" | "local_unverified";
  note: string | null;
  steps: string[];
  links: { label: string; url: string }[];
  supplement_warning: boolean;
  related_chunk_ids: string[];
  list_version: string;
  reviewed: boolean;
  data_sources: { label: string; url: string }[];
  candidates: { name: string; otc: string; ingredients: string[]; status: CheckStatus | null }[];
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  token?: string; // assistant 턴: 서버가 그 답을 줄 때 붙인 서명
}

export interface LibrarySection {
  id: string;
  heading: string;
  text: string;
}

export interface LibraryDocSummary {
  doc_id: string;
  title: string;
  source: string;
  url: string;
  version: string;
  category: string;
  summary: string | null;
  reviewed: boolean;
  section_headings: string[];
  length: number;
}

export interface LibraryDoc extends Omit<LibraryDocSummary, "section_headings" | "length"> {
  sections: LibrarySection[];
  quiz: { question: string; choices: string[]; answer: number; explanation: string } | null;
}

export type ReviewStatus = "reviewed" | "needs_fix" | "none";
export interface LessonReview {
  status: ReviewStatus;
  note: string | null;
  at: string | null;
}

export interface Citation {
  chunk_id: string;
  source: "WADA" | "KADA" | "ADEL";
  title: string;
  url: string;
}

export interface ChatResponse {
  kind: "answer" | "fixed" | "server";
  answer: string;
  citations: Citation[];
  refer_to_expert: boolean;
  out_of_scope: boolean;
  guess: string; // AI 추측(교육 자료에 없는 내용)
  token: string;
  drug_checks: CheckResult[]; // 질문 속 약 이름의 조회표 판정
  related_lessons: { lesson_id: string; title: string; category: string }[]; // 답에 인용된 레슨
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

// 422(pydantic) 오류를 사람이 읽을 문장으로. 행 번호는 1부터.
function validationMessage(errors: { loc: (string | number)[]; msg: string }[]): string {
  return errors.map((e) => e.msg.replace(/^Value error, /, "")).join(" / ");
}

// 로그인이 끊겼을 때(12시간 지남, 코드 재발급) 로그인 화면으로 돌려보내는 곳. App이 등록한다.
let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn;
}

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    credentials: "same-origin",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 401 && path !== "/api/session") onUnauthorized();
  if (!res.ok) {
    const detail = await res.json().then(
      (d) => (typeof d.detail === "string" ? d.detail : Array.isArray(d.detail) ? validationMessage(d.detail) : ""),
      () => "",
    );
    throw new ApiError(res.status, detail || "요청을 처리하지 못했어요.");
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const api = {
  login: (code: string) => call<SessionInfo>("POST", "/api/session", { code }),
  whoami: () => call<SessionInfo>("GET", "/api/session"),
  logout: () => call<void>("DELETE", "/api/session"),
  demoCodes: () => call<DemoCode[]>("GET", "/api/demo/codes"),
  // 선수
  home: () => call<AthleteHome>("GET", "/api/athlete/home"),
  lesson: (id: string) => call<LessonView>("GET", `/api/athlete/lessons/${encodeURIComponent(id)}`),
  answerLesson: (id: string, choice: number) =>
    call<QuizResult>("POST", `/api/athlete/lessons/${encodeURIComponent(id)}/answer`, { lesson_id: id, choice }),
  answerSurprise: (id: string, choice: number) => call<QuizResult>("POST", "/api/athlete/quiz/answer", { lesson_id: id, choice }),
  survey: () => call<{ url: string }>("GET", "/api/athlete/survey"),
  history: () => call<AthleteHistory>("GET", "/api/athlete/history"),
  answerReview: (id: string, choice: number) => call<QuizResult>("POST", "/api/athlete/review/answer", { lesson_id: id, choice }),
  // 관리자
  overview: () => call<Overview>("GET", "/api/admin/overview"),
  athlete: (id: number) => call<AthleteDetail>("GET", `/api/admin/athletes/${id}`),
  createAthlete: (name: string, birth_year: number) => call<IssuedCode>("POST", "/api/admin/athletes", { name, birth_year }),
  reissueCode: (id: number) => call<IssuedCode>("POST", `/api/admin/athletes/${id}/code`),
  addRecord: (id: number, r: RecordInput) => call<AthleteDetail>("POST", `/api/admin/athletes/${id}/records`, r),
  deleteRecord: (id: number, recordId: number) => call<AthleteDetail>("DELETE", `/api/admin/athletes/${id}/records/${recordId}`),
  saveSettings: (s: ProgramSettings) => call<Overview>("PUT", "/api/admin/settings", s),
  rerank: () => call<Overview>("POST", "/api/admin/rerank"),
  library: () => call<LibraryDocSummary[]>("GET", "/api/library"),
  libraryDoc: (docId: string) => call<LibraryDoc>("GET", `/api/library/${encodeURIComponent(docId)}`),
  reviews: () => call<Record<string, LessonReview>>("GET", "/api/admin/reviews"),
  setReview: (id: string, status: ReviewStatus, note?: string) =>
    call<LessonReview>("PUT", `/api/admin/reviews/${encodeURIComponent(id)}`, { status, note: note ?? null }),
  // 공통
  chat: (messages: ChatMessage[]) => call<ChatResponse>("POST", "/api/chat", { messages }),
};
