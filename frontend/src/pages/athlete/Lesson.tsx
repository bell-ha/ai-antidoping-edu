import { ArrowLeft, ArrowRight } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { api, type AthleteHome, type LessonView, type QuizResult } from "../../api";
import { QuizBox } from "../../components/QuizBox";

export function Lesson() {
  const { lessonId = "" } = useParams();
  const [lesson, setLesson] = useState<LessonView | null>(null);
  const [answered, setAnswered] = useState(false);
  const [next, setNext] = useState<string | null>(null);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    setLesson(null);
    setAnswered(false);
    setError("");
    api.lesson(lessonId).then(setLesson, (e) => setError(e.message));
    window.scrollTo(0, 0);
  }, [lessonId]);

  const answer = (choice: number): Promise<QuizResult> =>
    api.answerLesson(lessonId, choice).then((r) => {
      setAnswered(true);
      api.home().then((h: AthleteHome) => setNext(h.lessons.find((l) => !l.completed)?.lesson_id ?? null));
      return r;
    });

  if (error) return <p className="error">{error}</p>;
  if (!lesson) return null;

  return (
    <article className="lesson stack-lg">
      <Link to="/home" className="btn-sub small" style={{ alignSelf: "flex-start" }}>
        <ArrowLeft size={14} /> 이번 주 목록
      </Link>
      <div className="stack" style={{ gap: 6 }}>
        <span className="caption">{lesson.category}</span>
        <h1 className="title">{lesson.title}</h1>
      </div>

      {lesson.sections.map((s) => (
        <section key={s.id} className="lesson-section">
          <h2 className="heading">{s.heading}</h2>
          <LessonText text={s.text} />
        </section>
      ))}

      <section className="card">
        <QuizBox q={lesson.quiz} onAnswer={answer} label={lesson.completed ? "퀴즈 (다시 풀기)" : "퀴즈 — 답하면 이 교육을 이수해요"} />
      </section>

      {answered && (
        <div className="row" style={{ justifyContent: "flex-end" }}>
          {next ? (
            <button className="btn" onClick={() => navigate(`/lesson/${next}`)}>
              다음 교육 <ArrowRight size={18} />
            </button>
          ) : (
            <Link className="btn" to="/home">
              이번 주 교육 끝! 목록으로
            </Link>
          )}
        </div>
      )}
    </article>
  );
}

/** 레슨 본문: 빈 줄로 문단, "- "는 목록, **굵게**, "출처:" 줄은 작게. */
function LessonText({ text }: { text: string }) {
  const blocks = text.split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean);
  return (
    <>
      {blocks.map((b, i) => {
        if (b.startsWith("출처:")) return <p key={i} className="caption lesson-source">{b}</p>;
        const lines = b.split("\n");
        if (lines.every((l) => l.trim().startsWith("- "))) {
          return (
            <ul key={i} className="lesson-ul">
              {lines.map((l, j) => (
                <li key={j}>{bold(l.trim().slice(2))}</li>
              ))}
            </ul>
          );
        }
        return <p key={i}>{bold(b)}</p>;
      })}
    </>
  );
}

function bold(s: string) {
  return s.split(/(\*\*[^*]+\*\*)/).map((part, i) => (part.startsWith("**") && part.endsWith("**") ? <b key={i}>{part.slice(2, -2)}</b> : part));
}
