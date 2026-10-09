import { createContext, useContext } from "react";
import type { Role, SessionInfo } from "./api";

export interface SessionState {
  who: SessionInfo;
  demo: boolean;
  logout: () => void;
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
