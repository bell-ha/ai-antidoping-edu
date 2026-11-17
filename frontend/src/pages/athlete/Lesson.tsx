import { ArrowLeft, ArrowRight } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router";
import { api, type AthleteHome, type LessonView, type QuizResult } from "../../api";
import { QuizBox } from "../../components/QuizBox";
import { RichText } from "../../components/RichText";

export function Lesson() {
  const { lessonId = "" } = useParams();
  const [lesson, setLesson] = useState<LessonView | null>(null);
  const [answered, setAnswered] = useState(false);
  const [next, setNext] = useState<string | null>(null);
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const fromAsk = (useLocation().state as { from?: string } | null)?.from === "ask"; // 질문하기의 관련 교육에서 들어옴

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
      {fromAsk ? (
        <button className="btn-sub small" style={{ alignSelf: "flex-start" }} onClick={() => navigate(-1)}>
          <ArrowLeft size={14} /> 질문으로 돌아가기
        </button>
      ) : (
        <Link to="/home" className="btn-sub small" style={{ alignSelf: "flex-start" }}>
          <ArrowLeft size={14} /> 이번 주 목록
        </Link>
      )}
      <div className="stack" style={{ gap: 6 }}>
        <span className="caption">{lesson.category.replace(/^[A-M] /, "")}</span>
        <h1 className="title">{lesson.title}</h1>
      </div>

      {lesson.sections.map((s) => (
        <section key={s.id} className="lesson-section">
          <h2 className="heading">{s.heading}</h2>
          <RichText text={s.text} />
        </section>
      ))}

      <section className="card">
        <QuizBox q={lesson.quiz} onAnswer={answer} label={lesson.completed ? "퀴즈 (이미 완료한 교육 · 다시 풀기)" : "퀴즈 — 답하면 맞든 틀리든 이 교육은 완료예요"} />
      </section>

      {answered && (
        <div className="row" style={{ justifyContent: "flex-end" }}>
          {next ? (
            <button className="btn" onClick={() => navigate(`/lesson/${next}`, { replace: true })} /* 이어 듣기는 바꿔 끼움 → 뒤로가기 한 번이면 목록 */>
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
