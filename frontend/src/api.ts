// backend/app/schemas.py와 같은 모양. 바꾸면 양쪽을 같이 고친다.

export type Role = "athlete" | "coach" | "support";
export type ProfileTag = "rapid_improvement" | "decline" | "weight_change" | "high_level" | "baseline";
export type CheckStatus = "PROHIBITED" | "IN_COMPETITION_ONLY" | "THRESHOLD" | "CONDITIONAL" | "NOT_LISTED_VERIFY" | "UNKNOWN";
export type Timing = "in_competition" | "out_of_competition" | "unknown";

export interface SessionInfo {
  role: Role;
  athlete_id: string | null;
  label: string;
}

export interface DemoPersona {
  code: string;
  info: SessionInfo;
  description: string;
}

export interface RecordPoint {
  date: string;
  competition_category: CompetitionCategory;
  weight_class: number;
  body_weight: number;
  snatch: number;
  clean_jerk: number;
  total: number;
}

export interface ForecastPoint {
  date: string;
  mean: number;
  lo: number;
  hi: number;
}

export interface Recommendation {
  content_id: string;
  title: string;
  summary: string;
  suggested_question: string;
}

export interface AthleteProfile {
  athlete_id: string;
  sport: string;
  sex: "M" | "F";
  age: number;
  weight_class: number;
  competition_category: CompetitionCategory;
  model: "rnn" | "synthetic_trend" | "none";
  notices: string[];
  records: RecordPoint[];
  forecast: ForecastPoint[];
  tags: ProfileTag[];
  tag_labels: string[];
  reasons: { tag: ProfileTag; text: string }[];
  checks: { tag: ProfileTag; label: string; met: boolean; detail: string }[];
  recommendations: Recommendation[];
  residuals: ResidualPoint[];
  model_result: ModelResult | null; // 연구진 모델 결과 모양(D35)
}

export interface ModelResult {
  athlete_id: string;
  model_version: string;
  source: "researchers" | "platform_temporary" | "synthetic" | "none";
  prediction: { target: "total"; unit: "kg"; value: number | null };
  observed: { value: number | null };
  residual_observed_minus_predicted: number | null;
  history_count: number;
  prediction_interval_kg: number | null;
  data_warnings: string[];
  profile_purpose: string;
}

export interface ResidualPoint {
  date: string;
  observed: number;
  predicted: number;
  diff_kg: number;
}


export type CompetitionCategory = "world" | "continent" | "other_international" | "domestic";

export interface RecordInput {
  date: string; // "YYYY-MM"
  competition_category: CompetitionCategory;
  body_weight: number;
  snatch: number;
  clean_jerk: number;
}

export interface DemoScenario {
  id: string;
  label: string;
  description: string;
  sex: "M" | "F";
  expect: ProfileTag[];
  expect_labels: string[];
  warnings: ("ratio" | "jump")[];
}

export interface DemoScenarios {
  model: "synthetic_trend" | "rnn";
  scenarios: DemoScenario[];
}

export interface ComputeRequest {
  sex: "M" | "F";
  birth_year: number;
  records: RecordInput[];
  confirmed?: boolean;
}

export interface InputWarning {
  row: number | null;
  field: string | null;
  code: "ratio" | "jump";
  message: string;
}

export interface ComputeResponse {
  profile: AthleteProfile | null;
  warnings: InputWarning[];
}

export interface Ingredient {
  name_ko: string;
  name_en: string;
  status: CheckStatus;
  wada_class: string | null;
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
  route: "kada" | "globaldro" | "local_unverified";
  steps: string[];
  links: { label: string; url: string }[];
  supplement_warning: boolean;
  related_chunk_ids: string[];
  list_version: string;
  reviewed: boolean;
  data_sources: { label: string; url: string }[];
  candidates: { name: string; otc: string; ingredients: string[] }[];
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  token?: string; // assistant 턴: 서버가 그 답을 줄 때 붙인 서명(D33)
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
  roles: Role[];
  topic: string | null;
  summary: string | null;
  reviewed: boolean;
  section_headings: string[];
  length: number;
}

export interface LibraryDoc extends Omit<LibraryDocSummary, "section_headings" | "length"> {
  sections: LibrarySection[];
}

export interface Citation {
  chunk_id: string;
  source: "WADA" | "KADA" | "ADEL" | "GlobalDRO";
  title: string;
  url: string;
}

export interface ChatResponse {
  kind: "answer" | "fixed" | "server";
  answer: string;
  citations: Citation[];
  refer_to_expert: boolean;
  out_of_scope: boolean;
  token: string;
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
  return errors
    .map((e) => {
      const row = e.loc.indexOf("records") >= 0 ? e.loc[e.loc.indexOf("records") + 1] : undefined;
      const msg = e.msg.replace(/^Value error, /, "");
      return typeof row === "number" ? `${row + 1}번째 기록: ${msg}` : msg;
    })
    .join(" / ");
}

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    credentials: "same-origin",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
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
  personas: () => call<DemoPersona[]>("GET", "/api/demo/personas"),
  compute: (req: ComputeRequest) => call<ComputeResponse>("POST", "/api/profile/compute", req),
  demoScenarios: () => call<DemoScenarios>("GET", "/api/demo/examples"),
  demoExample: (athleteId: string) => call<ComputeRequest>("GET", `/api/demo/examples/${encodeURIComponent(athleteId)}`),
  check: (query: string, country: string, timing: Timing) => call<CheckResult>("POST", "/api/check", { query, country, timing }),
  library: () => call<LibraryDocSummary[]>("GET", "/api/library"),
  libraryDoc: (docId: string) => call<LibraryDoc>("GET", `/api/library/${encodeURIComponent(docId)}`),
  survey: () => call<{ url: string }>("GET", "/api/survey"),
  chat: (messages: ChatMessage[], check_result?: CheckResult) =>
    call<ChatResponse>("POST", "/api/chat", { messages, context: check_result ? { check_result } : null }),
};
