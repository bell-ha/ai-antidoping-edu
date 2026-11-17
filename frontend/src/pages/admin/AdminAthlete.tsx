import { Archive, ArrowLeft, KeyRound, Pencil, Plus, Trash2 } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router";
import { api, type AthleteDetail, type CompetitionCategory, type IssuedCode, type RecordInput } from "../../api";
import { CodeHandoff } from "../../components/CodeHandoff";
import { Dialog } from "../../components/Dialog";
import { Select } from "../../components/Select";
import { CATEGORY_LABEL, MODEL_LABEL, weightClassLabel } from "../../session";

const EMPTY: RecordInput = { date: "", competition_category: "domestic", body_weight: 0, snatch: 0, clean_jerk: 0 };

export function AdminAthlete() {
  const id = Number(useParams().athleteId);
  const [d, setD] = useState<AthleteDetail | null>(null);
  const [error, setError] = useState("");
  const [issued, setIssued] = useState<IssuedCode | null>(null);
  const [tab, setTab] = useState<"chats" | "quizzes" | "lessons">("chats");
  const [notice, setNotice] = useState(""); // 기록을 넣거나 지운 뒤 단계가 바뀌었으면 알림(테스터 3·4)
  // 기록 추가·삭제 결과: 이 선수의 단계가 바뀌었는지 알려 준다(다른 선수도 다시 나눠짐)
  const changed = (next: AthleteDetail) => {
    const before = d?.athlete.tier ?? null;
    const after = next.athlete.tier;
    setNotice(before !== after ? `이 선수: ${before ?? "없음"} → ${after ?? "없음"}단계. 전체 선수도 다시 나눴어요.` : "전체 선수를 다시 나눴어요(이 선수 단계는 그대로).");
    setD(next);
  };
  const rename = () => {
    const name = window.prompt("새 이름", d?.athlete.name ?? "")?.trim();
    if (name) api.updateAthlete(id, { name }).then(setD, (e) => setError(e.message));
  };
  const archive = (active: boolean) =>
    window.confirm(active ? "보관을 풀까요? 다시 목록과 단계 나누기에 들어가고 로그인할 수 있어요." : "보관할까요? 목록과 단계 나누기에서 빠지고 이 선수는 로그인할 수 없어요. 기록은 지우지 않아요.") &&
    api.updateAthlete(id, { active }).then(setD, (e) => setError(e.message));

  useEffect(() => {
    api.athlete(id).then(setD, (e) => setError(e.message));
  }, [id]);

  if (error && !d) return <p className="error">{error}</p>;
  if (!d) return null;
  const a = d.athlete;
  const m = d.model_result;

  return (
    <>
      <Link to="/admin" className="btn-sub small" style={{ alignSelf: "flex-start", marginBottom: 16 }}>
        <ArrowLeft size={14} /> 선수 목록
      </Link>
      <div className="page-head page-head-row">
        <div className="stack" style={{ gap: 4 }}>
          <h1 className="title">
            {a.name} <span className="muted">{a.number}</span>
          </h1>
          <p className="muted">
            {a.birth_year}년생 · {weightClassLabel(a.weight_class)} · {a.tier !== null ? `${a.tier}단계 · 순위 ${a.rank}` : "단계 없음"} · 이번 주{" "}
            {a.week_done}/{a.week_total} · 마지막 접속일 {a.last_visit ? a.last_visit.slice(0, 10) : "없음"}
          </p>
        </div>
        <div className="row wrap" style={{ gap: 8 }}>
        <button className="btn-sub" onClick={rename}>
          <Pencil size={14} /> 이름 고치기
        </button>
        <button className="btn-sub" onClick={() => archive(!a.active)}>
          <Archive size={14} /> {a.active ? "보관(목록에서 빼기)" : "보관 풀기"}
        </button>
        <button
          className="btn-sub"
          onClick={() => window.confirm("새 코드를 발급하면 지금 코드는 바로 쓸 수 없어요. 발급할까요?") && api.reissueCode(id).then(setIssued, (e) => setError(e.message))}
        >
          <KeyRound size={14} /> 로그인 코드 새로 발급
        </button>
        </div>
      </div>
      {error && <p className="error" style={{ marginBottom: 16 }}>{error}</p>}
      {notice && <p className="notice notice-neutral" style={{ marginBottom: 16 }}>{notice}</p>}

      <div className="grid">
        <section className="span-4 stack-lg">
          <div className="card stack">
            <h2 className="heading">연구진 모델 결과</h2>
            {m ? (
              <dl className="kv">
                <dt>마지막 대회 합계</dt>
                <dd>{m.observed.value ?? "—"}kg</dd>
                <dt>모델 예측</dt>
                <dd>{m.prediction.value ?? "—"}{m.prediction.value !== null && "kg"}</dd>
                <dt>실제 − 예측</dt>
                <dd>
                  <b>
                    {m.residual_observed_minus_predicted === null
                      ? "—"
                      : `${m.residual_observed_minus_predicted > 0 ? "+" : ""}${m.residual_observed_minus_predicted}kg`}
                  </b>
                </dd>
                <dt>예측에 쓴 이전 대회</dt>
                <dd>{m.history_count}개</dd>
                <dt>모델</dt>
                <dd className="caption">{MODEL_LABEL[m.source] ?? m.model_version}</dd>
              </dl>
            ) : (
              <p className="muted">아직 결과가 없어요.</p>
            )}
            {m?.data_warnings.map((w) => (
              <p key={w} className="caption">
                {w}
              </p>
            ))}
          </div>
          <div className="card stack">
            <h2 className="heading">교육 현황</h2>
            <dl className="kv">
              <dt>이수한 교육</dt>
              <dd>{a.lessons_completed}개</dd>
              <dt>퀴즈 정답 / 오답</dt>
              <dd>
                {a.quiz_correct} / {a.quiz_wrong}
              </dd>
              <dt>오답 남음(다시 풀기 전)</dt>
              <dd>{a.wrong_open}개</dd>
              <dt>질문</dt>
              <dd>{a.questions}개</dd>
              <dt>첫 안내</dt>
              <dd>
                {a.onboarding === "finished" ? "끝까지 봄" : a.onboarding === "skipped" ? "건너뜀" : "아직"}
                {a.onboarding_at && <span className="muted"> · {a.onboarding_at.slice(0, 10)}</span>}
              </dd>
            </dl>
          </div>
        </section>

        <section className="span-8 stack-lg">
          <Records d={d} onChange={changed} />

          <div className="card stack">
            <div className="row wrap" style={{ gap: 8 }}>
              {(
                [
                  ["chats", `질문 ${d.chats.length}`],
                  ["quizzes", `퀴즈 ${d.quizzes.length}`],
                  ["lessons", `교육 배정 ${d.lessons.length}`],
                ] as const
              ).map(([k, label]) => (
                <button key={k} className={`chip ${tab === k ? "chip-on" : "chip-plain"}`} onClick={() => setTab(k)}>
                  {label}
                </button>
              ))}
            </div>
            {tab === "chats" &&
              (d.chats.length ? (
                d.chats.map((c, i) => (
                  <div key={i} className="chat-log-item">
                    <span className="caption">{c.at.slice(0, 16).replace("T", " ")}</span>
                    <p className="bubble-user">{c.question}</p>
                    <p className="answer">{c.answer}</p>
                  </div>
                ))
              ) : (
                <p className="muted">아직 질문이 없어요.</p>
              ))}
            {tab === "quizzes" && (
              <table className="data-table">
                <tbody>
                  {d.quizzes.map((q, i) => (
                    <tr key={i}>
                      <td>{q.at.slice(0, 16).replace("T", " ")}</td>
                      <td>{{ lesson: "교육 퀴즈", surprise: "깜짝 퀴즈", review: "오답 다시 풀기", retry: "이수 후 다시 풀기" }[q.context]}</td>
                      <td>{q.title}</td>
                      <td>{q.correct ? "정답" : `오답(${q.choice}번)`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {tab === "lessons" && (
              <table className="data-table">
                <tbody>
                  {d.lessons.map((l) => (
                    <tr key={l.lesson_id}>
                      <td>{l.week_start} 주</td>
                      <td>{l.lesson_id}</td>
                      <td>{l.title}</td>
                      <td>{l.completed_at ? `이수 ${l.completed_at.slice(0, 10)}` : "아직"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>
      </div>

      {issued && (
        <Dialog onClose={() => setIssued(null)} persistent>
          <h2 className="heading">새 로그인 코드</h2>
          <p className="muted">이전 코드는 이제 쓸 수 없어요. 새 코드는 지금만 볼 수 있으니 복사하거나 안내문을 그대로 보내 주세요.</p>
          <CodeHandoff name={a.name} code={issued.code} onClose={() => setIssued(null)} />
        </Dialog>
      )}
    </>
  );
}

function Records({ d, onChange }: { d: AthleteDetail; onChange: (d: AthleteDetail) => void }) {
  const [r, setR] = useState<RecordInput>(EMPTY);
  const [error, setError] = useState("");
  const id = d.athlete.id;
  const [busy, setBusy] = useState(false); // 연타로 같은 기록이 두 번 들어가던 문제(테스터 2)
  const dateOk = /^\d{4}-(0[1-9]|1[0-2])$/.test(r.date);
  const valid = dateOk && r.body_weight > 0 && r.snatch > 0 && r.clean_jerk > 0;
  // 버튼이 회색이기만 하고 이유가 안 보이던 문제(테스터 2·3)
  const why = r.date && !dateOk ? "대회 연월은 2025-03처럼 넣어 주세요." : "";

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    const warn = [
      r.snatch > r.clean_jerk && `인상(${r.snatch})이 용상(${r.clean_jerk})보다 커요.`,
      d.records.some((x) => x.date === r.date) && `${r.date}에 이미 기록이 있어요.`,
    ].filter(Boolean);
    if (warn.length && !window.confirm(`${warn.join(" ")} 그래도 넣을까요?`)) return;
    setError("");
    setBusy(true);
    api.addRecord(id, r).then(
      (x) => {
        onChange(x);
        setR(EMPTY);
      },
      (e) => setError(e.message),
    ).finally(() => setBusy(false));
  };
  const num = (k: "body_weight" | "snatch" | "clean_jerk") => (e: React.ChangeEvent<HTMLInputElement>) =>
    setR({ ...r, [k]: Number(e.target.value) || 0 });

  return (
    <div className="card stack">
      <h2 className="heading">경기 기록</h2>
      <p className="caption">기록을 넣거나 지우면 이 선수의 모델을 다시 돌리고 전체 선수의 단계를 다시 나눠요. 예측에는 대회 기록이 3개(마지막 1개 + 이전 2개) 이상 필요해요.</p>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>대회 연월</th>
              <th>대회</th>
              <th className="num">계체</th>
              <th>체급</th>
              <th className="num">인상</th>
              <th className="num">용상</th>
              <th className="num">합계</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {d.records.map((x) => (
              <tr key={x.id}>
                <td>{x.date}</td>
                <td>{CATEGORY_LABEL[x.competition_category]}</td>
                <td className="num">{x.body_weight}</td>
                <td>{weightClassLabel(x.weight_class)}</td>
                <td className="num">{x.snatch}</td>
                <td className="num">{x.clean_jerk}</td>
                <td className="num">
                  <b>{x.total}</b>
                </td>
                <td>
                  <button className="icon-btn" aria-label="기록 지우기" onClick={() => window.confirm(`${x.date} 기록(합계 ${x.total}kg)을 지울까요? 전체 선수의 단계를 다시 나눠요.`) && api.deleteRecord(id, x.id).then(onChange, (e) => setError(e.message))}>
                    <Trash2 size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <form className="record-add" onSubmit={submit}>
        <input className="input" placeholder="대회 연월(2025-03)" value={r.date} onChange={(e) => setR({ ...r, date: e.target.value })} aria-label="대회 연월" />
        <Select<CompetitionCategory>
          id="category"
          value={r.competition_category}
          onChange={(v) => setR({ ...r, competition_category: v })}
          options={(Object.keys(CATEGORY_LABEL) as CompetitionCategory[]).map((value) => ({ value, label: CATEGORY_LABEL[value] }))}
          label="대회 종류"
        />
        <input className="input" inputMode="decimal" placeholder="계체(kg)" value={r.body_weight || ""} onChange={num("body_weight")} aria-label="계체 체중" />
        <input className="input" inputMode="numeric" placeholder="인상" value={r.snatch || ""} onChange={num("snatch")} aria-label="인상" />
        <input className="input" inputMode="numeric" placeholder="용상" value={r.clean_jerk || ""} onChange={num("clean_jerk")} aria-label="용상" />
        <button className="btn" style={{ height: 44 }} disabled={!valid || busy}>
          <Plus size={16} /> {busy ? "넣는 중…" : "추가"}
        </button>
      </form>
      {why && <p className="caption">{why}</p>}
      {error && <p className="error">{error}</p>}
    </div>
  );
}
