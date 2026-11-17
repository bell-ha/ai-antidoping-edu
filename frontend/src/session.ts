import { createContext, useContext } from "react";
import type { CompetitionCategory, Role, SessionInfo } from "./api";

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

// 역할별 메뉴: 선수는 교육·질문만, 관리자는 선수 관리와 도구
export const NAV_BY_ROLE: Record<Role, { path: string; label: string }[]> = {
  athlete: [
    { path: "/home", label: "교육 시작하기" },
    { path: "/ask", label: "질문하기" },
    { path: "/history", label: "내 학습 기록" },
    { path: "/guide", label: "사용 설명서" },
  ],
  admin: [
    { path: "/admin", label: "선수 관리" },
    { path: "/admin/settings", label: "단계 설정" },
    { path: "/library", label: "교육 자료" },
    { path: "/ask", label: "질문하기" },
    { path: "/architecture", label: "시스템 구성" },
  ],
};

export const HOME_BY_ROLE: Record<Role, string> = { athlete: "/home", admin: "/admin" };

export function weightClassLabel(wc: number | null): string {
  if (wc === null) return "—";
  if (wc === 999) return "+109kg급"; // 2018 IWF 남자 최상위 체급
  return `${wc}kg급`;
}

export const CATEGORY_LABEL: Record<CompetitionCategory, string> = {
  world: "세계대회",
  continent: "대륙대회",
  other_international: "그 밖의 국제대회",
  domestic: "국내 대회",
};

// 예측 모델 이름(서버 adapter.MODEL_LABEL과 같음). 화면마다 이름이 달라 연구진 가중치인지 알 수 없다는 지적(테스터 1·2·13)
export const MODEL_LABEL: Record<string, string> = {
  researchers: "연구진 RNN(LSTM)",
  platform_temporary: "연구진 RNN(LSTM) · 인계 코드로 재현한 임시 가중치(남자)",
  synthetic: "공개용 합성 모델(연구진 모델 아님)",
  none: "모델 없음",
};
