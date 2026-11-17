import { ArrowLeft, ArrowRight, X } from "lucide-react";
import { useEffect, useState } from "react";
import type { GuideStep } from "../content/guide";
import { Dialog } from "./Dialog";

export type OnboardingOutcome = "finished" | "skipped";

/** 카드 몇 장을 차례로 보여 주는 첫 안내. ←/→로 넘기고 Esc·바깥 누르기·건너뛰기는 "skipped". */
export function Onboarding({
  slides,
  finishLabel,
  onFinish,
  onHome,
  onSkip,
}: {
  slides: GuideStep[];
  finishLabel: string;
  onFinish: () => void; // 마지막 장의 큰 버튼
  onHome?: () => void; // 마지막 장의 작은 버튼(없으면 숨김)
  onSkip: () => void;
}) {
  const [i, setI] = useState(0);
  const last = i === slides.length - 1;
  const { icon: Icon, title, body } = slides[i];

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") setI((n) => Math.min(n + 1, slides.length - 1));
      if (e.key === "ArrowLeft") setI((n) => Math.max(n - 1, 0));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [slides.length]);

  return (
    <Dialog onClose={onSkip} className="onboarding" label="처음 안내">
      <div className="onboarding-top">
        <span className="caption">
          {i + 1} / {slides.length}
        </span>
        <button className="onboarding-skip" onClick={onSkip}>
          건너뛰기 <X size={14} />
        </button>
      </div>

      <div className="onboarding-slide" aria-live="polite">
        <span className="onboarding-icon">
          <Icon size={32} />
        </span>
        <h2 className="title">{title}</h2>
        <p className="muted">{body}</p>
      </div>

      <div className="onboarding-dots" aria-hidden>
        {slides.map((s, n) => (
          <span key={s.title} className={n === i ? "on" : undefined} />
        ))}
      </div>

      <div className="onboarding-actions">
        {i > 0 ? (
          <button className="btn-sub" onClick={() => setI(i - 1)}>
            <ArrowLeft size={16} /> 이전
          </button>
        ) : (
          <span />
        )}
        {last ? (
          <div className="row" style={{ gap: 8 }}>
            {onHome && (
              <button className="btn-sub" onClick={onHome}>
                홈으로
              </button>
            )}
            <button className="btn" onClick={onFinish} autoFocus>
              {finishLabel} <ArrowRight size={16} />
            </button>
          </div>
        ) : (
          <button className="btn" onClick={() => setI(i + 1)} autoFocus>
            다음 <ArrowRight size={16} />
          </button>
        )}
      </div>
    </Dialog>
  );
}
