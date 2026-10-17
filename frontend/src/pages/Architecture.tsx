import { ArrowDown, ArrowRight, BookOpen, Brain, Database, Globe, Lock, Monitor, Server, Sparkles, type LucideIcon } from "lucide-react";
import { Fragment } from "react";

// 발표용 시스템 구성도. 실데이터 수치(모델 성능·코호트 수)는 넣지 않는다 — 구조와 흐름만.

type Kind = "ai" | "rule" | "data" | "ext";

const KIND: Record<Kind, { label: string; icon: LucideIcon }> = {
  ai: { label: "AI", icon: Sparkles },
  rule: { label: "규칙", icon: Server },
  data: { label: "자료", icon: Database },
  ext: { label: "외부", icon: Globe },
};

interface Lane {
  id: string;
  title: string;
  users: string;
  screen: string[];
  steps: { label: string; kind: Kind }[];
  sources: { label: string; detail: string; kind: Kind }[];
  note: string;
}

const LANES: Lane[] = [
  {
    id: "tier",
    title: "① 단계 나누기",
    users: "관리자",
    screen: ["선수 등록 · 로그인 코드 발급", "경기 기록 입력 · 단계 설정 · 진행 현황"],
    steps: [
      { label: "경기력 예측", kind: "ai" },
      { label: "관측 − 예측", kind: "rule" },
      { label: "줄 세우기", kind: "rule" },
      { label: "단계 배정", kind: "rule" },
    ],
    sources: [
      { label: "연구진 RNN", detail: "LSTM · 연구진이 학습 · 플랫폼은 결과만 사용", kind: "ai" },
      { label: "단계 설정", detail: "단계 수 · 주당 교육 수 · 퀴즈 빈도 (관리자)", kind: "data" },
    ],
    note: "예측보다 기록이 많이 오른 선수일수록 높은 단계 · 결과 없으면 가장 낮은 단계",
  },
  {
    id: "lesson",
    title: "② 교육 시작하기",
    users: "선수",
    screen: ["이번 주 교육 목록", "교육 글 · 객관식 퀴즈 · 갑자기 퀴즈"],
    steps: [
      { label: "주간 배정", kind: "rule" },
      { label: "교육 읽기", kind: "rule" },
      { label: "퀴즈 채점", kind: "rule" },
      { label: "갑자기 퀴즈", kind: "rule" },
    ],
    sources: [
      { label: "교육 300개", detail: "WADA ISE·Athlete Curriculum·ADEL 구조 · KADA 자료 근거", kind: "data" },
      { label: "학습 기록", detail: "이수 · 정답/오답 · 접속 (운영 DB)", kind: "data" },
    ],
    note: "단계가 높을수록 한 주 교육 수 · 퀴즈 확률 · 문항 수가 많음 · 갑자기 퀴즈는 배운 교육에서만",
  },
  {
    id: "ask",
    title: "③ 질문하기",
    users: "선수 · 관리자",
    screen: ["약 이름(제품명·성분명) · 규정 질문", "답변 · 출처 표시"],
    steps: [
      { label: "질문 점검", kind: "rule" },
      { label: "약 이름 찾기", kind: "rule" },
      { label: "자료 검색", kind: "rule" },
      { label: "답변 생성", kind: "ai" },
    ],
    sources: [
      { label: "WADA 2026 금지목록", detail: "원문 PDF에서 추출 · S0~S9 · P1 · M1~M3", kind: "data" },
      { label: "국내 의약품 목록", detail: "심평원 약가마스터 · 제품명 → 성분", kind: "data" },
      { label: "Claude API", detail: "Anthropic 생성형 AI", kind: "ai" },
    ],
    note: "선수 이름·기록·단계는 AI에 보내지 않음 · 종목마다 다른 규정은 ‘종목마다 다르다’ · 경기기간 중/외 둘 다",
  },
];

const AI_ROLES = [
  {
    name: "연구진 RNN",
    type: "예측 모델 (LSTM)",
    does: "지난 대회 기록으로 마지막 대회 합계를 예측 → 실제와의 차이(관측 − 예측)",
    input: "대회별 합계 · 대회 수준 · 나이 · 연도",
    not: "도핑 여부를 판단하지 않음 · 플랫폼이 학습·조정하지 않음",
  },
  {
    name: "Claude",
    type: "생성형 AI (LLM)",
    does: "검색된 교육 자료와 약물 판정을 바탕으로 질문에 답하고 출처를 붙임",
    input: "질문 · 검색된 교육 자료 · 약물 조회표 판정",
    not: "약물 판정을 바꾸지 않음 · 선수 개인정보를 받지 않음 · 근거 없는 답은 차단",
  },
];

const NOT_AI = [
  { name: "줄 세우기 · 단계", does: "모델의 관측 − 예측으로 전원을 줄 세우고 단계 수만큼 고르게 나눔" },
  { name: "주간 배정 · 퀴즈", does: "단계별 개수만큼 교육을 순서대로 배정, 객관식 채점, 갑자기 퀴즈는 틀린 것 먼저" },
  { name: "약물 판정", does: "제품명을 성분으로 바꾼 뒤 금지목록으로 상태를 정함 (상시 금지 · 경기기간 중 금지 · 기준치 · 조건부 · 목록에 없음)" },
  { name: "자료 검색", does: "질문과 가까운 교육 조각을 찾음 (BM25, 한국어 글자 단위)" },
  { name: "질문 점검", does: "검사 회피·강요 질문을 걸러 고정 응답으로 보냄" },
];

const STACK = [
  { layer: "화면", tech: "React · TypeScript · Vite", note: "반응형 웹 (PC · 태블릿 · 휴대폰)" },
  { layer: "서버", tech: "Python · FastAPI", note: "화면과 API를 한 서버에서 제공" },
  { layer: "경기력 예측", tech: "연구진 RNN 가중치 · numpy 추론", note: "모델 파일은 레포 밖 비공개 폴더" },
  { layer: "자료 검색", tech: "BM25 · 동의어 사전", note: "외부 검색 서비스 없음" },
  { layer: "생성형 AI", tech: "Claude API (Anthropic)", note: "구조화 응답 · 인용 검증" },
  { layer: "운영 DB", tech: "SQLite", note: "선수 · 기록 · 단계 · 이수 · 퀴즈 · 질문" },
  { layer: "배포", tech: "Docker Compose", note: "서버 1개 · 로그인 코드" },
];

function KindTag({ kind }: { kind: Kind }) {
  const { label, icon: Icon } = KIND[kind];
  return (
    <span className={`arch-kind k-${kind}`}>
      <Icon size={12} />
      {label}
    </span>
  );
}

export function Architecture() {
  return (
    <>
      <div className="page-head">
        <h1 className="title">시스템 구성</h1>
        <p className="muted">화면 · 서버 · AI · 자료가 어떻게 이어지고 데이터가 어디로 흐르는지 보여줘요.</p>
      </div>

      <div className="stack-lg">
        <section className="card arch-card" data-figure="architecture">
          <div className="arch-legend">
            {(Object.keys(KIND) as Kind[]).map((k) => (
              <KindTag key={k} kind={k} />
            ))}
            <span className="caption">AI는 두 곳(경기력 예측, 답변 생성)에만 쓰고, 단계·판정·채점은 규칙이 정해요.</span>
          </div>

          <div className="arch" role="table" aria-label="시스템 구성도">
            <div className="arch-head" role="row">
              <span role="columnheader">
                <Monitor size={16} /> 사용자 · 화면
              </span>
              <span aria-hidden />
              <span role="columnheader">
                <Server size={16} /> 서버 처리 (FastAPI)
              </span>
              <span aria-hidden />
              <span role="columnheader">
                <Brain size={16} /> AI 모델 · 자료
              </span>
            </div>

            <div className="arch-session" role="row">
              <Lock size={16} aria-hidden />
              <span role="cell">
                <strong>로그인 코드</strong> · 가입 없음, 관리자가 발급 · 역할(선수 · 관리자)은 서버가 정함
              </span>
            </div>

            {LANES.map((l) => (
              <div key={l.id} className="arch-lane" role="row">
                <div className="arch-cell arch-screen" role="cell">
                  <p className="arch-lane-title">{l.title}</p>
                  <p className="caption">{l.users}</p>
                  <ul>
                    {l.screen.map((s) => (
                      <li key={s}>{s}</li>
                    ))}
                  </ul>
                </div>
                <Arrow />
                <div className="arch-cell" role="cell">
                  <ol className="arch-steps">
                    {l.steps.map((s, i) => (
                      <Fragment key={s.label}>
                        {i > 0 && <ArrowRight size={14} className="arch-step-arrow" aria-hidden />}
                        <li className={`arch-step k-${s.kind}`}>
                          {s.kind === "ai" && <Sparkles size={13} />}
                          {s.label}
                        </li>
                      </Fragment>
                    ))}
                  </ol>
                  <p className="caption arch-note">{l.note}</p>
                </div>
                <Arrow both />
                <div className="arch-cell" role="cell">
                  <ul className="arch-sources">
                    {l.sources.map((s) => (
                      <li key={s.label} className={`k-${s.kind}`}>
                        <KindTag kind={s.kind} />
                        <div>
                          <strong>{s.label}</strong>
                          <span className="caption">{s.detail}</span>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            ))}

            <div className="arch-link" role="row">
              <ArrowDown size={16} aria-hidden />
              <span role="cell">
                ①의 <strong>단계</strong>가 ②의 교육량과 퀴즈 빈도를 정해요. ③ 질문하기에는 선수 정보가 넘어가지 않아요.
              </span>
            </div>
          </div>
        </section>

        <div className="grid">
          <section className="card span-7" data-figure="ai-roles">
            <h2 className="heading">AI가 하는 일과 하지 않는 일</h2>
            <div className="table-scroll">
              <table className="arch-table">
                <thead>
                  <tr>
                    <th>AI</th>
                    <th>하는 일</th>
                    <th>입력</th>
                    <th>하지 않는 일</th>
                  </tr>
                </thead>
                <tbody>
                  {AI_ROLES.map((r) => (
                    <tr key={r.name}>
                      <td>
                        <strong>{r.name}</strong>
                        <span className="caption">{r.type}</span>
                      </td>
                      <td data-label="하는 일">{r.does}</td>
                      <td data-label="입력">{r.input}</td>
                      <td data-label="하지 않는 일">{r.not}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="card span-5">
            <h2 className="heading">AI가 아닌 부분 (규칙)</h2>
            <ul className="arch-plain">
              {NOT_AI.map((n) => (
                <li key={n.name}>
                  <strong>{n.name}</strong>
                  <span>{n.does}</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="card span-7">
            <h2 className="heading">기술 구성</h2>
            <div className="table-scroll">
              <table className="arch-table">
                <tbody>
                  {STACK.map((s) => (
                    <tr key={s.layer}>
                      <th scope="row">{s.layer}</th>
                      <td>{s.tech}</td>
                      <td className="caption">{s.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="card span-5">
            <h2 className="heading">
              <BookOpen size={18} style={{ verticalAlign: -3 }} /> 저장하는 것과 안 하는 것
            </h2>
            <ul className="arch-plain">
              <li>
                <strong>운영 DB에 저장</strong>
                <span>선수 이름 · 출생연도 · 경기 기록 · 모델 결과 · 단계 · 교육 이수 · 퀴즈 · 질문과 답 · 접속</span>
              </li>
              <li>
                <strong>저장하지 않음</strong>
                <span>로그인 코드 원문 (해시만)</span>
              </li>
              <li>
                <strong>Claude API로 보내는 것</strong>
                <span>질문 · 검색된 교육 자료 · 약물 판정 (이름 · 기록 · 단계는 보내지 않음)</span>
              </li>
            </ul>
          </section>
        </div>
      </div>
    </>
  );
}

function Arrow({ both }: { both?: boolean }) {
  return (
    <div className="arch-arrow" aria-hidden>
      <ArrowRight size={18} className="h" />
      {both && <ArrowRight size={18} className="h back" />}
      <ArrowDown size={18} className="v" />
    </div>
  );
}
