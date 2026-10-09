import { CalendarX, CircleHelp, Gauge, OctagonX, SearchCheck, type LucideIcon } from "lucide-react";
import type { CheckStatus } from "../api";

// DESIGN.md 3절. "허용" 상태와 초록은 없다.
const STATUS: Record<CheckStatus, { label: string; icon: LucideIcon }> = {
  PROHIBITED: { label: "금지", icon: OctagonX },
  IN_COMPETITION_ONLY: { label: "경기기간 중 금지", icon: CalendarX },
  THRESHOLD: { label: "기준을 넘으면 금지", icon: Gauge },
  NOT_LISTED_VERIFY: { label: "목록에서 확인되지 않음 · 확인 필요", icon: SearchCheck },
  UNKNOWN: { label: "성분 확인 필요", icon: CircleHelp },
};

export function StatusBadge({ status, small }: { status: CheckStatus; small?: boolean }) {
  const { label, icon: Icon } = STATUS[status];
  return (
    <span className={`status st-${status}${small ? " small" : ""}`}>
      <Icon size={small ? 14 : 16} />
      {label}
    </span>
  );
}
