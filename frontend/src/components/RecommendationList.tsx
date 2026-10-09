import { ArrowRight } from "lucide-react";
import { useNavigate } from "react-router";
import type { Recommendation } from "../api";

export function RecommendationList({ items }: { items: Recommendation[] }) {
  const navigate = useNavigate();
  return (
    <div className="stack">
      {items.map((r) => (
        <button key={r.content_id} className="card-link" onClick={() => navigate("/learn", { state: { question: r.suggested_question } })}>
          <strong>{r.title}</strong>
          <span className="sub">{r.summary}</span>
          <span className="more">
            AI에게 물어보기 <ArrowRight size={16} />
          </span>
        </button>
      ))}
    </div>
  );
}
