import { ArrowRight, CircleCheck, CircleX, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router";
import { api, type AthleteHistory } from "../../api";
import { QuizBox } from "../../components/QuizBox";

/** 내 학습 기록: 들은 교육과 퀴즈 결과, 오답 다시 풀기(맞히면 목록에서 빠진다). */
export function History() {
  const [h, setH] = useState<AthleteHistory | null>(null);
  const [error, setError] = useState("");
  const [round, setRound] = useState(0); // 다시 풀기를 마치고 새로 불러올 때마다 퀴즈 상자를 새로 그린다

  useEffect(() => {
    api.history().then(setH, (e) => setError(e.message));
  }, [round]);

  if (error) return <p className="error">{error}</p>;
  if (!h) return null;

  const rate = h.quiz_correct + h.quiz_wrong ? Math.round((h.quiz_correct / (h.quiz_correct + h.quiz_wrong)) * 100) : null;

  return (
    <>
      <div className="page-head">
        <h1 className="title">내 학습 기록</h1>
        <p className="muted">들은 교육과 퀴즈 결과예요. 틀린 문제는 아래에서 다시 풀 수 있어요.</p>
      </div>

      <div className="stat-row">
        <div className="card stat">
          <span className="caption">들은 교육</span>
          <strong>
            {h.completed} <span className="muted">/ {h.lesson_total}</span>
          </strong>
        </div>
        <div className="card stat">
          <span className="caption">퀴즈 정답률</span>
          <strong>{rate === null ? "—" : `${rate}%`}</strong>
          <span className="caption">
            정답 {h.quiz_correct} · 오답 {h.quiz_wrong}
          </span>
        </div>
        <div className="card stat">
          <span className="caption">다시 풀 문제</span>
          <strong>{h.wrong.length}</strong>
        </div>
      </div>

      <section className="stack" style={{ marginTop: 32 }}>
        <h2 className="heading">
          <RotateCcw size={18} style={{ verticalAlign: -3 }} /> 오답 다시 풀기
        </h2>
        {h.wrong.length === 0 ? (
          <p className="muted">다시 풀 문제가 없어요.</p>
        ) : (
          <>
            {h.wrong.map((q) => (
              <section key={`${round}-${q.lesson_id}`} className="card">
                <QuizBox q={q} onAnswer={(c) => api.answerReview(q.lesson_id, c)} label={h.items.find((i) => i.lesson_id === q.lesson_id)?.title ?? "퀴즈"} />
              </section>
            ))}
            <button className="btn-sub" style={{ alignSelf: "flex-start" }} onClick={() => setRound((r) => r + 1)}>
              다 풀었어요 · 목록 새로 보기
            </button>
          </>
        )}
      </section>

      <section className="stack" style={{ marginTop: 32 }}>
        <h2 className="heading">들은 교육</h2>
        {h.items.length === 0 ? (
          <p className="muted">아직 들은 교육이 없어요.</p>
        ) : (
          <div className="lesson-list">
            {[...h.items].reverse().map((i) => (
              <Link key={i.lesson_id} className="lesson-row" to={`/lesson/${i.lesson_id}`}>
                {i.last_correct === false ? <CircleX size={18} className="mark-wrong" /> : <CircleCheck size={18} />}
                <span className="lesson-text">
                  <span className="lesson-cat">{i.category}</span>
                  <span className="lesson-title">{i.title}</span>
                </span>
                <span className="caption">{i.completed_at.slice(0, 10)}</span>
                <ArrowRight size={16} />
              </Link>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
