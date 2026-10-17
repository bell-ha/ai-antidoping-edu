import { CircleCheck, CircleX } from "lucide-react";
import { useState } from "react";
import type { QuizQuestion, QuizResult } from "../api";

/** 객관식 1문항. 고르면 바로 채점 결과와 해설을 보여 준다(정답은 서버만 안다). */
export function QuizBox({ q, onAnswer, label = "퀴즈" }: { q: QuizQuestion; onAnswer: (choice: number) => Promise<QuizResult>; label?: string }) {
  const [picked, setPicked] = useState<number | null>(null);
  const [result, setResult] = useState<QuizResult | null>(null);
  const [error, setError] = useState("");

  const pick = (choice: number) => {
    if (result || picked !== null) return;
    setPicked(choice);
    onAnswer(choice).then(setResult, (e) => {
      setPicked(null);
      setError(e.message);
    });
  };

  return (
    <div className="quiz stack">
      <span className="label">{label}</span>
      <p className="quiz-q">{q.question}</p>
      <div className="quiz-choices">
        {q.choices.map((c, i) => {
          const n = i + 1;
          const state = !result ? "" : n === result.answer ? " right" : n === picked ? " wrong" : " dim";
          return (
            <button key={n} className={`quiz-choice${state}`} onClick={() => pick(n)} disabled={!!result || picked !== null}>
              <span className="quiz-num">{n}</span>
              <span>{c}</span>
            </button>
          );
        })}
      </div>
      {error && <p className="error">{error}</p>}
      {result && (
        <div className={`notice ${result.correct ? "notice-right" : "notice-wrong"}`}>
          {result.correct ? <CircleCheck size={18} /> : <CircleX size={18} />}
          <span>
            <b>{result.correct ? "정답이에요." : `정답은 ${result.answer}번이에요.`}</b> {result.explanation}
          </span>
        </div>
      )}
    </div>
  );
}
