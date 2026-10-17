import { ArrowRight, BookOpen } from "lucide-react";
import { Link, useNavigate } from "react-router";
import type { Recommendation } from "../api";

// 추천 교육 카드: 자료를 직접 읽거나, AI에게 추천 질문으로 묻는다. content_id = knowledge/ 문서 ID
export function RecommendationList({ items }: { items: Recommendation[] }) {
  const navigate = useNavigate();
  return (
    <div className="cards-3">
      {items.map((r) => (
        <div key={r.content_id} className="card-soft">
          <strong>{r.title}</strong>
          <span className="muted">{r.summary}</span>
          <span className="row wrap" style={{ gap: 6, marginTop: "auto" }}>
            <Link className="more" to={`/library/${r.content_id}`}>
              <BookOpen size={16} /> 자료 읽기
            </Link>
            <button type="button" className="more" onClick={() => navigate("/learn", { state: { question: r.suggested_question } })}>
              AI에게 물어보기 <ArrowRight size={16} />
            </button>
          </span>
        </div>
      ))}
    </div>
  );
}
