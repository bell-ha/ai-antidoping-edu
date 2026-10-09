import { Info } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type AthleteProfile } from "../api";
import { RecommendationList } from "../components/RecommendationList";
import { RecordChart } from "../components/RecordChart";

const LEVEL: Record<AthleteProfile["competition_level"], string> = { junior: "주니어", national: "국내 대회", international: "국제 대회" };

export function Performance() {
  const [p, setP] = useState<AthleteProfile | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.me().then(setP, (e) => setError(e.message));
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (!p) return null;

  return (
    <>
      {/* 설명은 한 줄로 유지: 1280×800 첫 화면에 태그·추천 이유·차트가 다 들어와야 한다 */}
      <div className="page-head">
        <h1 className="title">나의 교육 프로파일</h1>
        <p className="muted">경기 기록의 변화에 맞춰 지금 필요한 반도핑 교육을 추천해요.</p>
      </div>

      <div className="grid">
        <section className="card span-8" data-figure="chart">
          <h2 className="heading">경기 기록과 예측</h2>
          <RecordChart records={p.records} forecast={p.forecast} />
        </section>

        <div className="span-4 stack-lg" data-figure="profile">
          <section className="card">
            <h2 className="heading">교육 프로파일</h2>
            <p className="muted num">
              {p.age}세 · {p.sex === "M" ? "남자" : "여자"} {p.weight_class}kg급 · {LEVEL[p.competition_level]}
            </p>
            <div className="row wrap">
              {p.tags.map((t, i) => (
                <span key={t} className="chip chip-app">
                  {p.tag_labels[i] ?? t}
                </span>
              ))}
            </div>
          </section>

          <section className="card">
            <h2 className="heading">추천 이유</h2>
            <div className="stack">
              {p.reasons.map((r) => (
                <div key={r.tag} className="row" style={{ alignItems: "flex-start" }}>
                  <Info size={18} style={{ flex: "none", marginTop: 4, color: "var(--app-ink)" }} />
                  <span className="num">{r.text}</span>
                </div>
              ))}
            </div>
          </section>
        </div>

        <section className="span-12 stack-lg" style={{ marginTop: 16 }}>
          <h2 className="heading">추천 교육</h2>
          <RecommendationList items={p.recommendations} />
        </section>
      </div>
    </>
  );
}
