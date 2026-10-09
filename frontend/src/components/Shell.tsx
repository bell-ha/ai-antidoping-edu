import { ChartLine, GraduationCap, LogOut, Pill, Users, type LucideIcon } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router";
import { TABS_BY_ROLE, useSession, type TabKey } from "../session";
import { Sheet } from "./Sheet";

const TAB: Record<TabKey, { path: string; label: string; icon: LucideIcon }> = {
  performance: { path: "/performance", label: "경기력", icon: ChartLine },
  team: { path: "/team", label: "팀 교육", icon: Users },
  check: { path: "/check", label: "약물 확인", icon: Pill },
  learn: { path: "/learn", label: "AI 교육", icon: GraduationCap },
};

export function Shell() {
  const { who, demo, logout } = useSession();
  const [confirming, setConfirming] = useState(false);

  return (
    <div className="app">
      <header className="topbar">
        <span className="topbar-title">AI 반도핑 교육</span>
        <button className="chip chip-plain" onClick={() => setConfirming(true)} aria-label={`${who.label} · 나가기`}>
          {who.label}
          <LogOut size={14} />
        </button>
      </header>

      <main className="main">
        <Outlet />
        <p className="footnote">{demo && "합성 데이터 · "}연구용 프로토타입 · 최종 확인은 KADA</p>
      </main>

      <nav className="tabbar">
        {TABS_BY_ROLE[who.role].map((key) => {
          const { path, label, icon: Icon } = TAB[key];
          return (
            <NavLink key={key} to={path} className={({ isActive }) => `tab${isActive ? " active" : ""}`}>
              <Icon size={22} />
              {label}
            </NavLink>
          );
        })}
      </nav>

      {confirming && (
        <Sheet onClose={() => setConfirming(false)}>
          <h2 className="heading">나갈까요?</h2>
          <p className="sub">다시 들어오려면 접근 코드를 입력해야 해요.</p>
          <div className="grid-2">
            <button className="btn-sub" onClick={() => setConfirming(false)}>
              취소
            </button>
            <button className="btn" style={{ height: 44 }} onClick={logout}>
              나가기
            </button>
          </div>
        </Sheet>
      )}
    </div>
  );
}
