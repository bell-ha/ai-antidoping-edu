import { createContext, useContext } from "react";
import type { AthleteProfile, Role, SessionInfo } from "./api";

export interface SessionState {
  who: SessionInfo;
  demo: boolean;
  logout: () => void;
  // 직접 입력으로 계산한 프로파일. 브라우저 메모리에만 있고 새로고침하면 사라진다 (D25)
  profile: AthleteProfile | null;
  setProfile: (p: AthleteProfile | null) => void;
}

export const SessionContext = createContext<SessionState | null>(null);

export function useSession(): SessionState {
  const s = useContext(SessionContext);
  if (!s) throw new Error("SessionContext 밖에서 사용됨");
  return s;
}

// DESIGN.md 2절 역할별 탭
export type TabKey = "performance" | "team" | "check" | "learn";

export const TABS_BY_ROLE: Record<Role, TabKey[]> = {
  athlete: ["performance", "check", "learn"],
  coach: ["team", "check", "learn"],
  support: ["check", "learn"],
};

export const HOME_BY_ROLE: Record<Role, string> = {
  athlete: "/performance",
  coach: "/team",
  support: "/check",
};

export function weightClassLabel(sex: "M" | "F", wc: number): string {
  if (wc === 999) return sex === "M" ? "+109kg급" : "+87kg급"; // 2018 IWF 최상위 체급
  return `${wc}kg급`;
}
