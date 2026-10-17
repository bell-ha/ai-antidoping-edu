import { LogOut } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { NavLink, Outlet } from "react-router";
import { NAV_BY_ROLE, useSession } from "../session";
import { Dialog } from "./Dialog";

export function Shell() {
  const { who, demo, logout } = useSession();
  const [confirming, setConfirming] = useState(false);
  const [survey, setSurvey] = useState("");

  useEffect(() => {
    if (who.role === "athlete") api.survey().then((s) => setSurvey(s.url), () => setSurvey(""));
  }, [who.role]);

  return (
    <>
      <header className="nav">
        <div className="container nav-inner">
          <span className="brand">AI 반도핑 교육</span>
          <nav className="nav-links" aria-label="주 메뉴">
            {NAV_BY_ROLE[who.role].map((n) => (
              <NavLink key={n.path} to={n.path} end={n.path === "/admin"} className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
                {n.label}
              </NavLink>
            ))}
          </nav>
          <div className="nav-right">
            <span className="chip chip-plain">{who.role === "admin" ? `관리자 · ${who.label}` : who.label}</span>
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
          {demo && "더미 데이터 · "}연구용 프로토타입
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
          <p className="muted">다시 들어오려면 로그인 코드를 입력해야 해요.</p>
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
