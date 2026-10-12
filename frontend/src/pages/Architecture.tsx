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
    id: "profile",
    title: "① 교육 프로파일",
    users: "선수",
    screen: ["최근 대회 기록 3~10개 직접 입력", "태그 · 추천 이유 · 추천 교육"],
    steps: [
      { label: "입력 검증", kind: "rule" },
      { label: "경기력 예측", kind: "ai" },
      { label: "태그 규칙", kind: "rule" },
      { label: "교육 추천", kind: "rule" },
    ],
    sources: [
      { label: "연구진 RNN", detail: "LSTM · IWF 국제대회 기록으로 학습", kind: "ai" },
      { label: "태그·추천 규칙", detail: "±2σ · 계체 ±5kg · 세계·대륙대회", kind: "data" },
    ],
    note: "기록은 저장하지 않음 · 세션에는 태그·나이대·대회 수준만",
  },
  {
    id: "check",
    title: "② 약물 확인",
    users: "선수 · 지도자 · 지원인력",
    screen: ["국내 제품명·성분명 · 구매 국가 · 사용 시기", "상태 배지 · 확인 절차 · 공식 링크"],
    steps: [
      { label: "제품·성분 찾기", kind: "rule" },
      { label: "조회표 판정", kind: "rule" },
      { label: "확인 절차 안내", kind: "rule" },
    ],
    sources: [
      { label: "WADA 2026 금지목록", detail: "원문 PDF에서 추출 · 원문 색인 전수 대조", kind: "data" },
      { label: "국내 의약품 목록", detail: "심평원 약가마스터 · 제품명 → 성분 · 투여 경로", kind: "data" },
      { label: "성분·제품 조회표", detail: "자주 묻는 성분과 제품군", kind: "data" },
      { label: "KADA · Global DRO", detail: "최종 확인 링크", kind: "ext" },
    ],
    note: "판정은 조회표가 함 · AI는 판정하지 않음 · ‘허용’ 판정 없음",
  },
  {
    id: "learn",
    title: "③ AI 교육",
    users: "선수 · 지도자 · 지원인력",
    screen: ["질문 · 추천 질문", "답변 · 출처 표시 · 전문가 안내"],
    steps: [
      { label: "질문 점검", kind: "rule" },
      { label: "자료 검색", kind: "rule" },
      { label: "답변 생성", kind: "ai" },
      { label: "인용 검증", kind: "rule" },
    ],
    sources: [
      { label: "반도핑 교육 자료", detail: "KADA · WADA · Global DRO 문서 발췌", kind: "data" },
      { label: "Claude API", detail: "Anthropic 생성형 AI", kind: "ai" },
    ],
    note: "회피·강요 질문은 AI를 부르지 않고 고정 응답 · 출처 없는 답은 내보내지 않음",
  },
];

const AI_ROLES = [
  {
    name: "연구진 RNN",
    type: "예측 모델 (LSTM)",
    does: "지난 대회 기록으로 다음 대회 합계와 예측 범위를 계산",
    input: "대회별 합계 · 대회 수준 · 나이 · 연도",
    not: "도핑 여부를 판단하지 않음 · 제재 이력을 입력으로 쓰지 않음",
  },
  {
    name: "Claude",
    type: "생성형 AI (LLM)",
    does: "교육 프로파일과 검색된 공식 자료를 바탕으로 질문에 답하고 출처를 붙임",
    input: "질문 · 태그 · 나이대 · 대회 수준 · 검색된 자료",
    not: "약물 허용 여부를 판정하지 않음 · 원 기록을 받지 않음 · 근거 없는 답은 차단",
  },
];

const NOT_AI = [
  { name: "태그 규칙", does: "예측과 실제 기록의 차이(±2σ), 체중 변화, 국제대회 출전으로 태그를 붙임" },
  { name: "약물 판정", does: "제품명을 성분으로 바꾼 뒤 금지목록으로 상태를 정함 (금지 · 경기기간 중 금지 · 기준치 · 조건부 · 확인 필요). 같은 성분도 투여 경로(먹는 약 · 흡입 · 바르는 약)에 따라 달라짐" },
  { name: "자료 검색", does: "질문과 가까운 공식 자료 조각을 찾음 (BM25, 한국어 글자 단위)" },
  { name: "모델은 연구진 소관", does: "플랫폼은 연구진 예측 모델의 출력만 받아 교육을 구성함. 학습·성능 조정을 하지 않고, 도핑 분류·확률은 쓰지 않음" },
  { name: "질문 점검", does: "검사 회피·강요 질문을 걸러 고정 응답과 전문가 안내로 보냄" },
];

const STACK = [
  { layer: "화면", tech: "React · TypeScript · Vite", note: "반응형 웹 (PC · 태블릿 · 휴대폰)" },
  { layer: "서버", tech: "Python · FastAPI", note: "화면과 API를 한 서버에서 제공" },
  { layer: "경기력 예측", tech: "연구진 RNN 가중치 · numpy 추론", note: "모델 파일은 레포 밖 비공개 폴더" },
  { layer: "자료 검색", tech: "BM25 · 동의어 사전", note: "외부 검색 서비스 없음" },
  { layer: "생성형 AI", tech: "Claude API (Anthropic)", note: "구조화 응답 · 인용 검증" },
  { layer: "배포", tech: "Docker Compose", note: "컨테이너 1개 · 접근 코드" },
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
            <span className="caption">AI는 두 곳(경기력 예측, 답변 생성)에만 쓰고, 판정·태그는 규칙이 정해요.</span>
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
              <Lock size={16} />
              <span>
                <strong>접근 코드 로그인</strong> · 역할(선수 · 지도자 · 지원인력)과 선수 ID는 서버 세션에만 두고 화면에서 받지 않음
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
              <ArrowDown size={16} />
              <span>
                ①의 <strong>태그 · 나이대 · 대회 수준</strong>만 ③ AI 교육으로 넘어가 답변을 맞춤화해요. 대회 기록 원본은 넘어가지 않아요.
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
                <strong>저장하지 않음 (시범 운영 기준)</strong>
                <span>입력한 대회 기록 · 약물 검색어 · 질문 내용</span>
              </li>
              <li>
                <strong>서명된 세션 쿠키에만 (나가기를 누르면 삭제)</strong>
                <span>역할 · 태그 · 나이대 · 대회 수준</span>
              </li>
              <li>
                <strong>Claude API로 보내는 것</strong>
                <span>질문 · 태그 · 나이대 · 대회 수준 · 검색된 공식 자료 (이름 · 기록 원본은 보내지 않음)</span>
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
