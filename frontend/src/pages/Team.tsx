import { ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type TeamSummary } from "../api";
import { RecommendationList } from "../components/RecommendationList";

// D9: 주제만. 선수 이름·인원수·목록·표 없음 — 넓은 화면이라고 팀 표를 만들지 않는다.
export function Team() {
  const [team, setTeam] = useState<TeamSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.team().then(setTeam, (e) => setError(e.message));
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (!team) return null;

  return (
    <>
      <div className="page-head">
        <h1 className="title">팀에 추천되는 교육</h1>
        <p className="muted">팀 선수들의 교육 프로파일을 모아, 함께 다루면 좋은 주제를 보여드려요.</p>
      </div>
      <div className="stack-lg">
        <div className="notice notice-neutral">
          <ShieldCheck size={18} />
          <span>선수 개인의 교육 프로파일은 본인만 볼 수 있어요. 여기에는 팀에 필요한 교육 주제만 보여요.</span>
        </div>
        <RecommendationList items={team.topics} />
      </div>
    </>
  );
}
