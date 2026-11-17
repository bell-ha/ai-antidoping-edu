import { PlayCircle } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { Onboarding } from "../../components/Onboarding";
import { GUIDE_STEPS, introSlides } from "../../content/guide";

export function Guide() {
  const [intro, setIntro] = useState(false);
  const navigate = useNavigate();
  return (
    <>
      <div className="page-head page-head-row">
        <div className="stack" style={{ gap: 4 }}>
          <h1 className="title">사용 설명서</h1>
          <p className="muted">처음이라면 이것만 읽고 시작하세요.</p>
        </div>
        <button className="btn-sub" onClick={() => setIntro(true)}>
          <PlayCircle size={16} /> 처음 안내 다시 보기
        </button>
      </div>
      <div className="cards-2">
        {GUIDE_STEPS.map(({ icon: Icon, title, body }) => (
          <section key={title} className="card stack">
            <Icon size={24} />
            <h2 className="heading">{title}</h2>
            <p className="muted">{body}</p>
          </section>
        ))}
      </div>
      {/* 다시 보기는 서버에 기록하지 않는다(처음 기록만 연구 자료로 남김) */}
      {intro && <Onboarding slides={introSlides()} finishLabel="교육으로 가기" onFinish={() => navigate("/home", { replace: true })} onSkip={() => setIntro(false)} />}
    </>
  );
}
