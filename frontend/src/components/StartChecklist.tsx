import { ArrowRight, Circle, CircleCheck, ListChecks, PlayCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { api, type StartChecklist as Checklist } from "../api";
import { ADMIN_SLIDES } from "../content/guide";
import { Onboarding } from "./Onboarding";

/** 관리자 시작 체크리스트. 끝났는지는 서버가 실제 데이터로 정한다. reloadKey가 바뀌면(선수 등록 등) 다시 불러온다. */
export function StartChecklist({ reloadKey }: { reloadKey: unknown }) {
  const [data, setData] = useState<Checklist | null>(null);
  const [intro, setIntro] = useState<"first" | "again" | null>(null);
  const introShown = useRef(false); // 표를 다시 불러와도 첫 안내는 한 번만 띄운다

  useEffect(() => {
    api.checklist().then((c) => {
      setData(c);
      if (!c.intro_done && !introShown.current) {
        introShown.current = true;
        setIntro("first"); // 관리자 첫 로그인: 안내 카드 먼저
      }
    }, () => setData(null));
  }, [reloadKey]);

  if (!data) return null;
  const setHidden = (hidden: boolean) => api.setChecklist(hidden).then(() => setData({ ...data, hidden }));
  const closeIntro = (outcome: "finished" | "skipped") => {
    if (intro === "first") {
      api.adminOnboardingDone(outcome).catch(() => undefined); // 다시 보기는 기록하지 않는다
      setData({ ...data, intro_done: true });
    }
    setIntro(null);
  };
  const introDialog = intro && (
    <Onboarding slides={ADMIN_SLIDES} finishLabel="시작하기" onFinish={() => closeIntro("finished")} onSkip={() => closeIntro("skipped")} />
  );
  const again = (
    <button className="onboarding-skip" onClick={() => setIntro("again")}>
      <PlayCircle size={14} /> 관리자 안내 다시 보기
    </button>
  );

  if (data.hidden)
    return (
      <div className="row" style={{ gap: 12, marginBottom: 16 }}>
        <button className="chip chip-plain" onClick={() => setHidden(false)}>
          <ListChecks size={14} /> 시작 체크리스트 보기
        </button>
        {again}
        {introDialog}
      </div>
    );

  const done = data.items.filter((i) => i.done).length;
  return (
    <section className="card stack checklist" style={{ marginBottom: 24 }}>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
        <h2 className="heading">
          시작 체크리스트 <span className="muted">{done}/{data.items.length}</span>
        </h2>
        <div className="row" style={{ gap: 16 }}>
          {again}
          <button className="onboarding-skip" onClick={() => setHidden(true)}>
            숨기기
          </button>
        </div>
      </div>
      <p className="caption">{done === data.items.length ? "모두 끝났어요. 이제 선수들이 교육을 들을 수 있어요." : "위에서부터 차례로 하면 돼요."}</p>
      <ol className="checklist-items">
        {data.items.map((item) => (
          <li key={item.key} className={item.done ? "done" : undefined}>
            <Link to={item.link}>
              {item.done ? <CircleCheck size={18} /> : <Circle size={18} />}
              <span className="checklist-text">
                <strong>{item.label}</strong>
                <span className="caption">{item.detail}</span>
              </span>
              <ArrowRight size={16} />
            </Link>
          </li>
        ))}
      </ol>
      {introDialog}
    </section>
  );
}
