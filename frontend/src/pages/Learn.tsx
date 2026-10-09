import { CircleHelp, ExternalLink, Send, Stethoscope } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useLocation } from "react-router";
import { api, type AthleteProfile, type ChatMessage, type ChatResponse, type CheckResult, type Citation } from "../api";
import { Dialog } from "../components/Dialog";
import { useSession } from "../session";

const SOURCE_LABEL: Record<Citation["source"], string> = { WADA: "WADA", KADA: "KADA", ADEL: "ADEL", GlobalDRO: "Global DRO" };

const SUGGESTED: Record<string, string[]> = {
  athlete: ["프로틴 보충제 먹어도 돼?", "병원에서 약 처방받을 때 뭘 확인해야 해?", "도핑검사 받을 때 순서가 어떻게 돼?"],
  coach: ["프로틴 보충제 먹어도 돼?", "국제대회 전에 선수들과 뭘 점검해야 해?", "선수지원인력의 반도핑 책임은 뭐야?"],
  support: ["감기약에 든 슈도에페드린은 어떻게 규정돼 있어?", "TUE는 언제 신청해야 해?", "해외에서 산 약은 어떻게 확인해?"],
};

interface Turn {
  question: string;
  response?: ChatResponse;
  error?: string;
}

type LearnState = { question?: string; check?: CheckResult } | null;

export function Learn() {
  const { who } = useSession();
  const location = useLocation();
  const initial = location.state as LearnState;
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState(initial?.question ?? (initial?.check ? `“${initial.check.query}” 확인 결과를 쉽게 설명해줘` : ""));
  const [check] = useState<CheckResult | undefined>(initial?.check);
  const [pending, setPending] = useState(false);
  const [source, setSource] = useState<Citation | null>(null);
  const [profile, setProfile] = useState<AthleteProfile | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  // 선수는 본인 추천 교육의 질문을 앞에 둔다
  useEffect(() => {
    if (who.role === "athlete") api.me().then(setProfile, () => {});
  }, [who.role]);
  const suggestions = [...new Set([...(profile?.recommendations.map((r) => r.suggested_question) ?? []), ...SUGGESTED[who.role]])];

  useEffect(() => {
    if (turns.length) endRef.current?.scrollIntoView({ block: "nearest" });
  }, [turns]);

  const send = (question: string) => {
    if (!question.trim() || pending) return;
    const history: ChatMessage[] = turns.flatMap((t) =>
      t.response ? [{ role: "user" as const, content: t.question }, { role: "assistant" as const, content: t.response.answer }] : [],
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
        <h1 className="title">AI 맞춤형 교육</h1>
        <p className="muted">WADA·KADA 공식 자료에 근거해 답하고, 답마다 출처를 보여드려요.</p>
      </div>

      <div className="grid">
        <aside className="span-4 stack-lg">
          {profile && (
            <section className="card">
              <h2 className="heading">내 교육 프로파일</h2>
              <div className="row wrap">
                {profile.tags.map((t, i) => (
                  <span key={t} className="chip chip-app">
                    {profile.tag_labels[i] ?? t}
                  </span>
                ))}
              </div>
            </section>
          )}
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
            <p className="caption">이름, 소속, 연락처를 입력하지 마세요.</p>
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
          <a className="btn btn-block" href={source.url} target="_blank" rel="noreferrer">
            원문 보기 <ExternalLink size={18} />
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
      {r.kind === "answer" && r.refer_to_expert && (
        <div className="notice notice-caution">
          <Stethoscope size={18} />
          <span>전문가 확인이 필요한 질문이에요. KADA 또는 팀 닥터에게 확인하세요.</span>
        </div>
      )}
      {r.kind === "answer" && !r.refer_to_expert && r.out_of_scope && (
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
