import { ArrowRight, CircleHelp, ExternalLink, Send, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useLocation } from "react-router";
import { api, type ChatMessage, type ChatResponse, type CheckResult, type Citation } from "../api";
import { StatusBadge } from "../components/StatusBadge";
import { useSession } from "../session";

const SOURCE_LABEL: Record<Citation["source"], string> = { WADA: "WADA", KADA: "KADA", ADEL: "ADEL" };

const SUGGESTED = [
  "타이레놀 먹어도 돼?",
  "에페드린은 평소에 먹어도 돼?",
  "S6에 해당하는 약물은 뭐야?",
  "도핑검사는 불시에 할 수 있어?",
  "프로틴 보충제 먹어도 돼?",
  "병원에서 약 처방받을 때 뭘 확인해야 해?",
];

interface Turn {
  question: string;
  response?: ChatResponse;
  error?: string;
}

type AskState = { question?: string } | null;

export function Ask() {
  const location = useLocation();
  const initial = location.state as AskState;
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState(initial?.question ?? "");
  const [pending, setPending] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const suggestions = SUGGESTED;

  useEffect(() => {
    if (turns.length) endRef.current?.scrollIntoView({ block: "nearest" });
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

  const submit = (e: FormEvent) => {
    e.preventDefault();
    send(draft);
  };

  return (
    <>
      <div className="page-head">
        <h1 className="title">질문하기</h1>
        <p className="muted">약 이름(제품명이나 성분명)이나 도핑방지 규정을 물어보세요. WADA·KADA 자료에 근거해 답해요.</p>
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
                {t.error && <p className="error">{t.error}</p>}
                {!t.response && !t.error && <p className="caption">답변을 만들고 있어요…</p>}
              </div>
            ))}
            <div ref={endRef} />
          </div>

          <div className="composer">
            <form onSubmit={submit}>
              <input className="input" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="약 이름이나 도핑방지 규정을 물어보세요" aria-label="질문" />
              <button className="icon-btn" disabled={!draft.trim() || pending} aria-label="보내기">
                <Send size={18} />
              </button>
            </form>
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
      {/* 고정 응답·서버 문구는 본문에 이미 안내가 있으므로 배너를 붙이지 않는다 */}
      {r.kind === "answer" && r.out_of_scope && (
        <div className="notice notice-neutral">
          <CircleHelp size={18} />
          <span>교육 자료 범위 밖의 질문이에요.</span>
        </div>
      )}
      <p className="answer">{r.answer}</p>
      {r.drug_checks.length > 0 && <DrugCards checks={r.drug_checks} />}
      {r.related_lessons.length > 0 && (
        <div className="stack" style={{ gap: 6 }}>
          <span className="caption">관련 교육</span>
          <div className="related-list">
            {r.related_lessons.map((l) => (
              <Link key={l.lesson_id} className="related-lesson" to={who.role === "admin" ? `/library/${l.lesson_id}` : `/lesson/${l.lesson_id}`}>
                <span className="caption">{l.category}</span>
                <span>{l.title}</span>
                <ArrowRight size={14} />
              </Link>
            ))}
          </div>
        </div>
      )}
      {r.citations.length > 0 && (
        <div className="stack" style={{ gap: 6 }}>
          <span className="caption">출처 · 누르면 원문이 새 창으로 열려요</span>
          <div className="row wrap">
            {r.citations.map((c) => (
              <a key={c.chunk_id} className="chip-source" href={c.url} target="_blank" rel="noreferrer">
                <b>{SOURCE_LABEL[c.source]}</b>
                {c.title}
                <ExternalLink size={12} />
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

const KIND_LABEL: Record<CheckResult["matched_kind"], string> = { product: "제품", category: "제품군 · 여러 제품", substance: "성분", unmatched: "" };

/** 조회표 판정 원본(D38). AI 설명과 따로, 금지목록 조회표가 낸 그대로 보여 준다. */
function DrugCards({ checks }: { checks: CheckResult[] }) {
  return (
    <div className="drug-cards">
      <span className="caption">금지목록 조회표 판정 (2026)</span>
      {checks.map((c) => (
        <div key={c.query} className="drug-card">
          <div className="row wrap" style={{ gap: 8 }}>
            <strong>{c.matched_kind === "substance" && c.ingredients[0] ? c.ingredients[0].name_ko : c.query}</strong>
            <span className="caption">{KIND_LABEL[c.matched_kind]}</span>
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
          {c.supplement_warning && (
            <div className="notice notice-supplement">
              <TriangleAlert size={16} />
              <span>보충제는 성분표에 없는 금지물질이 섞여 있을 수 있어요(오염).</span>
            </div>
          )}
          {c.ingredients.map((i) => (
            <div key={i.name_en} className="drug-row">
              <span>
                {i.name_ko} <span className="caption">{i.name_en}{i.wada_class ? ` · ${i.wada_class}${i.wada_class_ko ? ` ${i.wada_class_ko}` : ""}` : ""}</span>
              </span>
              <StatusBadge status={i.status} small />
            </div>
          ))}
          {c.candidates.length > 0 && (
            <ul className="drug-candidates">
              {c.candidates.map((p) => (
                <li key={p.name}>
                  {p.name} <span className="caption">— {p.ingredients.join(", ")}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}
