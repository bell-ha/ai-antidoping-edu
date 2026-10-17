import { LogOut } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { NavLink, Outlet } from "react-router";
import { TABS_BY_ROLE, useSession, type TabKey } from "../session";
import { Dialog } from "./Dialog";

const NAV: Record<TabKey, { path: string; label: string }> = {
  performance: { path: "/performance", label: "경기력" },
  check: { path: "/check", label: "약물 확인" },
  learn: { path: "/learn", label: "AI 교육" },
  library: { path: "/library", label: "교육 자료" },
  architecture: { path: "/architecture", label: "시스템 구성" },
};

export function Shell() {
  const { who, demo, logout } = useSession();
  const [confirming, setConfirming] = useState(false);
  const [survey, setSurvey] = useState("");

  useEffect(() => {
    api.survey().then((s) => setSurvey(s.url), () => setSurvey(""));
  }, []);

  return (
    <>
      <header className="nav">
        <div className="container nav-inner">
          <span className="brand">AI 반도핑 교육</span>
          <nav className="nav-links" aria-label="주 메뉴">
            {TABS_BY_ROLE[who.role].map((key) => (
              <NavLink key={key} to={NAV[key].path} className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
                {NAV[key].label}
              </NavLink>
            ))}
          </nav>
          <div className="nav-right">
            <span className="chip chip-plain">{who.label}</span>
            <button className="btn-sub small" onClick={() => setConfirming(true)}>
              <LogOut size={14} /> 나가기
            </button>
          </div>
        </div>
      </header>

      <main className="container main">
        <Outlet />
      </main>

      <footer className="footer">
        <p className="container caption">
          {demo && "합성 데이터 · "}연구용 프로토타입
          {survey && (
            <>
              {" · "}
              <a href={survey} target="_blank" rel="noreferrer">
                연구 설문 참여하기
              </a>
            </>
          )}
        </p>
      </footer>

      {confirming && (
        <Dialog onClose={() => setConfirming(false)}>
          <h2 className="heading">나갈까요?</h2>
          <p className="muted">다시 들어오려면 접근 코드를 입력해야 해요.</p>
          <div className="row" style={{ justifyContent: "flex-end" }}>
            <button className="btn-sub" onClick={() => setConfirming(false)}>
              취소
            </button>
            <button className="btn" style={{ height: 40 }} onClick={logout}>
              나가기
            </button>
          </div>
        </Dialog>
      )}
    </>
  );
}
