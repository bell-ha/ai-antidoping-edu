import { BookOpen, CircleHelp, ExternalLink, Send } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useLocation } from "react-router";
import { api, type ChatMessage, type ChatResponse, type CheckResult, type Citation } from "../api";
import { Dialog } from "../components/Dialog";
import { useSession } from "../session";

const SOURCE_LABEL: Record<Citation["source"], string> = { WADA: "WADA", KADA: "KADA", ADEL: "ADEL", GlobalDRO: "Global DRO" };

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

type LearnState = { question?: string; check?: CheckResult } | null;

export function Ask() {
  const { who } = useSession();
  const location = useLocation();
  const initial = location.state as LearnState;
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState(initial?.question ?? (initial?.check ? `“${initial.check.query}” 확인 결과를 쉽게 설명해줘` : ""));
  const [check] = useState<CheckResult | undefined>(initial?.check);
  const [pending, setPending] = useState(false);
  const [source, setSource] = useState<Citation | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const suggestions = SUGGESTED;

  useEffect(() => {
    if (turns.length) endRef.current?.scrollIntoView({ block: "nearest" });
  }, [turns]);

  const send = (question: string) => {
    if (!question.trim() || pending) return;
    const history: ChatMessage[] = turns.flatMap((t) =>
      t.response ? [{ role: "user" as const, content: t.question }, { role: "assistant" as const, content: t.response.answer, token: t.response.token }] : [],
    );
    setTurns((ts) => [...ts, { question }]);
    setDraft("");
    setPending(true);
    api
      .chat([...history, { role: "user", content: question }], check)
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
                {t.response && <Answer r={t.response} onSource={setSource} />}
                {t.error && <p className="error">{t.error}</p>}
                {!t.response && !t.error && <p className="caption">답변을 만들고 있어요…</p>}
              </div>
            ))}
            <div ref={endRef} />
          </div>

          <div className="composer">
            <form onSubmit={submit}>
              <input className="input" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="반도핑에 대해 물어보세요" aria-label="질문" />
              <button className="icon-btn" disabled={!draft.trim() || pending} aria-label="보내기">
                <Send size={18} />
              </button>
            </form>
          </div>
        </section>
      </div>

      {source && (
        <Dialog onClose={() => setSource(null)}>
          <span className="chip-source" style={{ alignSelf: "flex-start" }}>
            <b>{SOURCE_LABEL[source.source]}</b>
          </span>
          <h2 className="heading">{source.title}</h2>
          {who.role === "admin" && (
            <Link className="btn btn-block" to={`/library/${source.chunk_id}`} onClick={() => setSource(null)}>
              교육 자료에서 읽기 <BookOpen size={18} />
            </Link>
          )}
          <a className="btn-sub" href={source.url} target="_blank" rel="noreferrer">
            원문 사이트 <ExternalLink size={14} />
          </a>
        </Dialog>
      )}
    </>
  );
}

function Answer({ r, onSource }: { r: ChatResponse; onSource: (c: Citation) => void }) {
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
      {r.citations.length > 0 && (
        <div className="row wrap">
          {r.citations.map((c) => (
            <button key={c.chunk_id} className="chip-source" onClick={() => onSource(c)}>
              <b>{SOURCE_LABEL[c.source]}</b>
              {c.title}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
