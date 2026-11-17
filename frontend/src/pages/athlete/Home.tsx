import { ArrowRight, CircleCheck, MessageCircle, PlayCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { api, type AthleteHome } from "../../api";
import { Dialog } from "../../components/Dialog";
import { Onboarding, type OnboardingOutcome } from "../../components/Onboarding";
import { QuizBox } from "../../components/QuizBox";
import { introSlides } from "../../content/guide";

export function Home() {
  const [home, setHome] = useState<AthleteHome | null>(null);
  const [error, setError] = useState("");
  const [quizOpen, setQuizOpen] = useState(false);
  const [quizIndex, setQuizIndex] = useState(0);
  const [introOpen, setIntroOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api.home().then(
      (h) => {
        setHome(h);
        setIntroOpen(!h.onboarding_done);
        setQuizOpen(h.onboarding_done && h.surprise_quiz.length > 0); // 첫 안내가 먼저, 끝나면 갑자기 퀴즈
      },
      (e) => setError(e.message),
    );
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (!home) return null;

  const todo = home.lessons.filter((l) => !l.completed);
  const done = home.lessons.filter((l) => l.completed);
  const next = todo[0];
  const quiz = home.surprise_quiz[quizIndex];

  const closeIntro = (outcome: OnboardingOutcome, goToLesson = false) => {
    api.onboardingDone(outcome).catch(() => undefined); // 기록 실패로 화면을 막지 않는다
    setIntroOpen(false);
    if (goToLesson && next) navigate(`/lesson/${next.lesson_id}`, { replace: true }); // 안내 칸을 레슨으로 바꿔 끼움 → 뒤로가기는 홈
    else setQuizOpen(home.surprise_quiz.length > 0);
  };

  return (
    <>
      <div className="page-head">
        <h1 className="title">{home.name}님, 이번 주 교육이에요</h1>
        <p className="muted">
          {home.week_start} 주 · 이번 주 {done.length}/{home.lessons.length}개 완료 · 전체 {home.completed_total}/{home.lesson_total}개 이수
        </p>
      </div>

      <div className="cards-2 home-actions">
        <button className="action-card" onClick={() => next && navigate(`/lesson/${next.lesson_id}`)} disabled={!next}>
          <PlayCircle size={28} />
          <strong>교육 시작하기</strong>
          <span className="muted">{next ? `다음: ${next.title}` : "이번 주 교육을 모두 들었어요."}</span>
        </button>
        <Link className="action-card" to="/ask">
          <MessageCircle size={28} />
          <strong>질문하기</strong>
          <span className="muted">약 이름이나 도핑방지 규정을 물어보세요.</span>
        </Link>
      </div>

      <section className="stack" style={{ marginTop: 32 }}>
        <h2 className="heading">이번 주 목록</h2>
        <div className="lesson-list">
          {home.lessons.map((l) => (
            <Link key={l.lesson_id} className={`lesson-row${l.completed ? " done" : ""}`} to={`/lesson/${l.lesson_id}`}>
              {l.completed ? <CircleCheck size={18} /> : <span className="lesson-dot" />}
              <span className="lesson-text">
                <span className="lesson-cat">{l.category}</span>
                <span className="lesson-title">{l.title}</span>
              </span>
              <ArrowRight size={16} />
            </Link>
          ))}
        </div>
      </section>

      {introOpen && (
        <Onboarding
          slides={introSlides(home.name, home.lessons.length)}
          finishLabel={next ? "첫 교육 시작하기" : "시작하기"}
          onFinish={() => closeIntro("finished", true)}
          onHome={next ? () => closeIntro("finished") : undefined}
          onSkip={() => closeIntro("skipped")}
        />
      )}

      {quizOpen && quiz && (
        <Dialog onClose={() => setQuizOpen(false)}>
          <h2 className="heading">
            갑자기 퀴즈! ({quizIndex + 1}/{home.surprise_quiz.length})
          </h2>
          <p className="caption">지금까지 배운 교육에서 나온 문제예요.</p>
          <QuizBox key={quiz.lesson_id} q={quiz} onAnswer={(c) => api.answerSurprise(quiz.lesson_id, c)} label="배운 교육에서 나온 문제" />
          <div className="row" style={{ justifyContent: "flex-end" }}>
            {quizIndex + 1 < home.surprise_quiz.length ? (
              <button className="btn" style={{ height: 40 }} onClick={() => setQuizIndex((i) => i + 1)}>
                다음 문제 <ArrowRight size={16} />
              </button>
            ) : (
              <button className="btn" style={{ height: 40 }} onClick={() => setQuizOpen(false)}>
                닫기
              </button>
            )}
          </div>
        </Dialog>
      )}
    </>
  );
}
