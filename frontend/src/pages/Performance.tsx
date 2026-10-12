import { Info } from "lucide-react";
import { useEffect, useRef } from "react";
import { RecommendationList } from "../components/RecommendationList";
import { RecordChart } from "../components/RecordChart";
import { RecordForm } from "../components/RecordForm";
import { CATEGORY_LABEL, useSession, weightClassLabel } from "../session";


// 어떤 모델로 계산했는지 그대로 밝힌다 (D26: 합성 기준인지 실제 데이터 기준인지)
function chartCaption(model: "rnn" | "synthetic_trend" | "none"): string {
  const base = "단위 kg · 2018 IWF 체급 기준 · 예측은 직전 기록 2개 이상부터";
  if (model === "rnn") return `${base} · 연구진 RNN(IWF 국제대회 기록으로 학습)`;
  if (model === "synthetic_trend") return `${base} · 합성 데이터 추세 모델(시연용)`;
  return "단위 kg · 2018 IWF 체급 기준 · 이 성별은 아직 경기력 예측 모델이 없어 기록만 보여줘요";
}

export function Performance() {
  const { profile: p, setProfile } = useSession();
  const resultRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (p) resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [p]);

  return (
    <>
      {/* 설명은 한 줄로 유지 */}
      <div className="page-head">
        <h1 className="title">나의 교육 프로파일</h1>
        <p className="muted">최근 대회 기록을 넣으면 경기력 변화에 맞춰 지금 필요한 반도핑 교육을 추천해요.</p>
      </div>

      <div className="stack-lg">
        <RecordForm onResult={setProfile} />

        {p && p.notices.length > 0 && (
          <div className="notice notice-neutral" role="status">
            <Info size={18} />
            <div className="stack" style={{ gap: 4 }}>
              {p.notices.map((n) => (
                <span key={n}>{n}</span>
              ))}
            </div>
          </div>
        )}
        {p && (
          <div className="grid" ref={resultRef} style={{ scrollMarginTop: 88 }}>
            <section className="card span-8" data-figure="chart">
              <h2 className="heading">{p.model === "none" ? "경기 기록" : "경기 기록과 예측"}</h2>
              <RecordChart records={p.records} forecast={p.forecast} caption={chartCaption(p.model)} />
            </section>

            <div className="span-4 stack-lg" data-figure="profile">
              <section className="card">
                <h2 className="heading">교육 프로파일</h2>
                <p className="muted num">
                  {p.age}세 · {p.sex === "M" ? "남자" : "여자"} {weightClassLabel(p.sex, p.weight_class)} · 최근 {CATEGORY_LABEL[p.competition_category]}
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
        )}
      </div>
    </>
  );
}
