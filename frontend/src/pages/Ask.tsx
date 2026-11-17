import { ArrowRight, ExternalLink, RotateCcw, Send, Sparkles, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useLocation } from "react-router";
import { api, type ChatMessage, type ChatResponse, type CheckResult } from "../api";
import { StatusBadge } from "../components/StatusBadge";
import { useSession } from "../session";

const SUGGESTED = [
  "타이레놀 먹어도 돼?",
  "에페드린은 평소에 먹어도 돼?",
  "감기약에 든 흥분제는 뭐야?",
  "수액이나 주사 맞아도 돼?",
  "도핑검사는 불시에 할 수 있어?",
  "프로틴 보충제 먹어도 돼?",
  "병원에서 약 처방받을 때 뭘 확인해야 해?",
];

const MAX_QUESTION = 500; // 서버 메시지 길이 제한과 맞춤

interface Turn {
  question: string;
  response?: ChatResponse;
  error?: string;
}

type AskState = { question?: string } | null;

// 관련 교육을 보고 뒤로가기로 돌아와도 대화가 남게 그 탭 안에만 보관한다(탭을 닫거나 로그아웃하면 지움 — 공용 기기 대비)
const STORE = "ask:turns";
export const clearAskHistory = () => {
  try {
    sessionStorage.removeItem(STORE);
  } catch {
    /* 저장소를 못 쓰는 브라우저: 보관 없이 동작 */
  }
};
const loadTurns = (): Turn[] => {
  try {
    return (JSON.parse(sessionStorage.getItem(STORE) ?? "[]") as Turn[]).filter((t) => t.response || t.error);
  } catch {
    return [];
  }
};

export function Ask() {
  const location = useLocation();
  const initial = location.state as AskState;
  const [turns, setTurns] = useState<Turn[]>(loadTurns);
  const [draft, setDraft] = useState(initial?.question ?? "");
  const [pending, setPending] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const suggestions = SUGGESTED;

  useEffect(() => {
    if (turns.length) endRef.current?.scrollIntoView({ block: "nearest" });
    try {
      sessionStorage.setItem(STORE, JSON.stringify(turns));
    } catch {
      /* 보관 실패는 무시 */
    }
  }, [turns]);

  const send = (question: string) => {
    if (!question.trim() || pending) return;
    // 서버가 AI에 보내는 것도 최근 2번뿐이라 그만큼만 보낸다(서버는 메시지 20개까지만 받는다)
    const history: ChatMessage[] = turns.slice(-2).flatMap((t) =>
      t.response ? [{ role: "user" as const, content: t.question }, { role: "assistant" as const, content: t.response.answer, token: t.response.token }] : [],
    );
    setTurns((ts) => [...ts, { question }]);
    setDraft("");
    setPending(true);
    api
      .chat([...history, { role: "user", content: question }])
      .then(
        (response) => setTurns((ts) => ts.map((t, i) => (i === ts.length - 1 ? { ...t, response } : t))),
        (e) => setTurns((ts) => ts.map((t, i) => (i === ts.length - 1 ? { ...t, error: e.message } : t))),
      )
      .finally(() => setPending(false));
  };

  const retry = (index: number) => {
    const question = turns[index].question;
    setTurns((ts) => ts.filter((_, i) => i !== index));
    send(question);
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    send(draft);
  };

  return (
    <>
      <div className="page-head">
        <h1 className="title">질문하기</h1>
        <p className="muted">
          약 이름(제품명이나 성분명)이나 도핑방지 규정을 물어보세요. AI가 WADA·KADA 교육 자료로 답을 만들어요. 답 아래 판정 카드는 금지목록
          규칙으로 정해지니, 글과 다르면 판정 카드를 따르세요.
        </p>
      </div>

      <div className="grid">
        <aside className="span-4 stack-lg">
          <section className="stack">
            <h2 className="label">추천 질문</h2>
            <div className="suggest-list">
              {suggestions.map((q) => (
                <button key={q} className="suggest" onClick={() => send(q)} disabled={pending}>
                  {q}
                </button>
              ))}
            </div>
          </section>
        </aside>

        <section className="card chat span-8" data-figure="chat">
          <div className="chat-log">
            {turns.length === 0 && <p className="chat-empty">추천 질문을 누르거나 아래에 질문을 입력해 보세요.</p>}
            {turns.map((t, i) => (
              <div key={i} className="stack" style={{ gap: 12 }}>
                <p className="bubble-user">{t.question}</p>
                {t.response && <Answer r={t.response} />}
                {t.error && (
                  <div className="row wrap" style={{ gap: 8 }}>
                    <p className="error">{t.error}</p>
                    <button className="btn-sub small" onClick={() => retry(i)} disabled={pending}>
                      <RotateCcw size={14} /> 다시 보내기
                    </button>
                  </div>
                )}
                {!t.response && !t.error && <p className="caption pending-dots">답변을 만들고 있어요(보통 5~15초)</p>}
              </div>
            ))}
            <div ref={endRef} />
          </div>

          <div className="composer">
            <form onSubmit={submit}>
              <input className="input" value={draft} maxLength={MAX_QUESTION} onChange={(e) => setDraft(e.target.value)}
                placeholder="예: 판콜 먹어도 돼?" aria-label="질문" />
              <button className="icon-btn" disabled={!draft.trim() || pending} aria-label="보내기">
                <Send size={18} />
              </button>
            </form>
            {draft.length > MAX_QUESTION - 100 && <span className="caption">{draft.length} / {MAX_QUESTION}자</span>}
          </div>
        </section>
      </div>

    </>
  );
}

function Answer({ r }: { r: ChatResponse }) {
  const { who } = useSession();
  return (
    <div className="answer-block">
      <p className="answer">{r.answer}</p>
      {r.guess && (
        <div className="guess">
          <span className="caption guess-label">
            <Sparkles size={14} /> 자료에 없는 AI 설명 · 확인되지 않은 내용이라 틀릴 수 있어요
          </span>
          <p>{r.guess}</p>
        </div>
      )}
      {r.drug_checks.length > 0 && <DrugCards checks={r.drug_checks} />}
      {r.related_lessons.length > 0 && (
        <div className="stack" style={{ gap: 6 }}>
          <span className="caption">관련 교육</span>
          <div className="related-list">
            {r.related_lessons.map((l) => (
              <Link key={l.lesson_id} className="related-lesson" to={who.role === "admin" ? `/library/${l.lesson_id}` : `/lesson/${l.lesson_id}`}
                state={{ from: "ask" }}>
                <span className="related-text">
                  <span className="caption">{l.category.replace(/^[A-M] /, "")}</span>
                  <span>{l.title}</span>
                </span>
                <ArrowRight size={14} />
              </Link>
            ))}
          </div>
        </div>
      )}
      {r.citations.length > 0 && (
        <div className="stack" style={{ gap: 6 }}>
          <span className="caption">답에 쓴 교육과 그 출처 · 누르면 원문 문서가 새 창으로 열려요</span>
          <div className="stack" style={{ gap: 6 }}>
            {r.citations.map((c) => (
              <a key={c.chunk_id} className="chip-source" href={c.url} target="_blank" rel="noreferrer">
                <b>교육</b>
                {c.title}
                <ExternalLink size={12} />
                {c.ref && <span className="chip-ref">출처: {c.ref}</span>}
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

const KIND_LABEL: Record<CheckResult["matched_kind"], string> = { product: "제품", category: "제품군 · 여러 제품", substance: "성분", unmatched: "" };

/** 조회표 판정 원본. AI 설명과 따로, 금지목록 조회표가 낸 그대로 보여 준다. */
function DrugCards({ checks }: { checks: CheckResult[] }) {
  return (
    <div className="drug-cards">
      <span className="caption">2026 금지목록 판정 · 금지목록 규칙으로 정해요(답 글과 다르면 이 판정을 따르세요)</span>
      {checks.map((c) => (
        <div key={c.query} className="drug-card">
          <div className="row wrap" style={{ gap: 8 }}>
            <strong>{c.matched_kind === "substance" && c.ingredients[0] ? c.ingredients[0].name_ko : c.query}</strong>
            <span className="caption">{KIND_LABEL[c.matched_kind]}</span>
            {c.matched_kind === "category" && <StatusBadge status={c.status} small />}
          </div>
          {c.matched_kind === "category" && c.ingredients.length > 0 && <span className="caption">일부 제품에 들어 있는 주의 성분</span>}
          {c.note && <span className="caption">{c.note}</span>}
          {c.links.length > 0 && (
            <div className="row wrap" style={{ gap: 8 }}>
              {c.links.map((l) => (
                <a key={l.url} className="caption" href={l.url} target="_blank" rel="noreferrer">
                  {l.label} <ExternalLink size={12} />
                </a>
              ))}
            </div>
          )}
          {c.supplement_warning && !c.note?.includes("섞여") && (
            <div className="notice notice-supplement">
              <TriangleAlert size={16} />
              <span>보충제는 성분표에 없는 금지물질이 섞여 있을 수 있어요(오염).</span>
            </div>
          )}
          {c.ingredients.map((i) => (
            <div key={i.name_en} className="drug-row">
              <span>
                {i.name_ko}{" "}
                <span className="caption">
                  {i.name_en.toLowerCase() !== i.name_ko.toLowerCase() ? i.name_en : ""}
                  {i.wada_class ? ` · ${i.wada_class}${i.wada_class_ko ? ` ${i.wada_class_ko}` : ""}` : ""}
                </span>
              </span>
              <StatusBadge status={i.status} small />
            </div>
          ))}
          {c.candidates.length > 0 && (
            <ul className="drug-candidates">
              {c.candidates.map((p) => (
                <li key={p.name} className="drug-candidate">
                  {/* 제품 이름과 배지를 한 줄로 묶는다(배지가 다음 제품 것처럼 보이던 문제, 테스터 7) */}
                  <div className="drug-candidate-head">
                    <strong>{p.name}</strong>
                    {p.status ? <StatusBadge status={p.status} small /> : <span className="caption">성분 정보 없음</span>}
                  </div>
                  <span className="caption">{p.ingredients.join(", ")}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}
