import { ArrowLeft, KeyRound, Plus, Trash2 } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router";
import { api, type AthleteDetail, type CompetitionCategory, type IssuedCode, type RecordInput } from "../../api";
import { Dialog } from "../../components/Dialog";
import { Select } from "../../components/Select";
import { CATEGORY_LABEL, weightClassLabel } from "../../session";

const EMPTY: RecordInput = { date: "", competition_category: "domestic", body_weight: 0, snatch: 0, clean_jerk: 0 };

export function AdminAthlete() {
  const id = Number(useParams().athleteId);
  const [d, setD] = useState<AthleteDetail | null>(null);
  const [error, setError] = useState("");
  const [issued, setIssued] = useState<IssuedCode | null>(null);
  const [tab, setTab] = useState<"chats" | "quizzes" | "lessons">("chats");

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
            {a.birth_year}년생 · {weightClassLabel(a.weight_class)} · {a.tier !== null ? `${a.tier}단계 (순위 ${a.rank})` : "단계 없음"} · 마지막 접속{" "}
            {a.last_visit ? a.last_visit.slice(0, 16).replace("T", " ") : "없음"}
          </p>
        </div>
        <button className="btn-sub" onClick={() => api.reissueCode(id).then(setIssued, (e) => setError(e.message))}>
          <KeyRound size={14} /> 로그인 코드 새로 발급
        </button>
      </div>

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
                <dt>관측 − 예측</dt>
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
                <dd className="caption">{m.model_version}</dd>
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
              <dt>질문</dt>
              <dd>{a.questions}개</dd>
            </dl>
          </div>
        </section>

        <section className="span-8 stack-lg">
          <Records d={d} onChange={setD} />

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
                      <td>{q.context === "surprise" ? "갑자기 퀴즈" : "교육 퀴즈"}</td>
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
        <Dialog onClose={() => setIssued(null)}>
          <h2 className="heading">새 로그인 코드</h2>
          <p className="muted">이전 코드는 이제 쓸 수 없어요. 지금만 볼 수 있으니 선수에게 전해 주세요.</p>
          <code className="issued-code">{issued.code}</code>
          <button className="btn" onClick={() => setIssued(null)}>
            닫기
          </button>
        </Dialog>
      )}
    </>
  );
}

function Records({ d, onChange }: { d: AthleteDetail; onChange: (d: AthleteDetail) => void }) {
  const [r, setR] = useState<RecordInput>(EMPTY);
  const [error, setError] = useState("");
  const id = d.athlete.id;
  const valid = /^\d{4}-(0[1-9]|1[0-2])$/.test(r.date) && r.body_weight > 0 && r.snatch > 0 && r.clean_jerk > 0;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setError("");
    api.addRecord(id, r).then(
      (x) => {
        onChange(x);
        setR(EMPTY);
      },
      (e) => setError(e.message),
    );
  };
  const num = (k: "body_weight" | "snatch" | "clean_jerk") => (e: React.ChangeEvent<HTMLInputElement>) =>
    setR({ ...r, [k]: Number(e.target.value) || 0 });

  return (
    <div className="card stack">
      <h2 className="heading">경기 기록</h2>
      <p className="caption">기록을 넣거나 지우면 이 선수의 모델을 다시 돌리고 전체 선수를 다시 줄 세워요.</p>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>대회 날짜</th>
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
                  <button className="icon-btn" aria-label="기록 지우기" onClick={() => api.deleteRecord(id, x.id).then(onChange, (e) => setError(e.message))}>
                    <Trash2 size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <form className="record-add" onSubmit={submit}>
        <input className="input" placeholder="YYYY-MM" value={r.date} onChange={(e) => setR({ ...r, date: e.target.value })} aria-label="대회 날짜" />
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
        <button className="btn" style={{ height: 44 }} disabled={!valid}>
          <Plus size={16} /> 추가
        </button>
      </form>
      {error && <p className="error">{error}</p>}
    </div>
  );
}
