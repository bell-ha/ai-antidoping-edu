import { ArrowRight, MessageCircle, Pill, TriangleAlert } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { api, type CheckResult, type Timing } from "../api";
import { Select } from "../components/Select";
import { StatusBadge } from "../components/StatusBadge";
import { useSession } from "../session";

// 국가는 화면 표시용. 경로(KADA / Global DRO / 그 외)는 서버가 정한다 (D12).
const COUNTRIES = [
  { value: "KR", label: "한국" },
  { value: "US", label: "미국" },
  { value: "JP", label: "일본" },
  { value: "CN", label: "중국" },
  { value: "GB", label: "영국" },
  { value: "CA", label: "캐나다" },
  { value: "AU", label: "호주" },
  { value: "FR", label: "프랑스" },
  { value: "DE", label: "독일" },
  { value: "TH", label: "태국" },
  { value: "VN", label: "베트남" },
  { value: "XX", label: "그 외 국가" },
];
const TIMINGS: { value: Timing; label: string }[] = [
  { value: "in_competition", label: "경기기간 중" },
  { value: "out_of_competition", label: "경기기간 외" },
  { value: "unknown", label: "잘 모르겠음" },
];

export function Check() {
  const { who } = useSession();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [country, setCountry] = useState("KR");
  const [timing, setTiming] = useState<Timing>("in_competition");
  const [result, setResult] = useState<CheckResult | null>(null);
  const [error, setError] = useState("");

  const run = (q: string) => {
    setError("");
    api.check(q, country, timing).then(setResult, (e) => setError(e.message));
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (query.trim()) run(query.trim());
  };

  const showCodes = who.role === "support"; // 선수지원인력에게는 조항 코드 (DESIGN.md 6절)

  return (
    <>
      <div className="page-head">
        <h1 className="title">약물·보충제 확인</h1>
        <p className="muted">먹기 전에 금지목록 기준으로 확인할 점과 공식 확인 절차를 알려드려요.</p>
      </div>

      <div className="grid">
        <form className="card span-5 sticky" onSubmit={submit}>
          <h2 className="heading">AI 약물 확인</h2>
          <div className="field">
            <label className="label" htmlFor="q">
              제품명 또는 성분명
            </label>
            <input id="q" className="input" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="예: 타이레놀콜드-에스정, 슈도에페드린, letrozole" autoComplete="off" />
          </div>
          <div className="fields-2">
            <div className="field">
              <label className="label" htmlFor="country">
                구매 국가
              </label>
              <Select id="country" value={country} options={COUNTRIES} onChange={setCountry} />
            </div>
            <div className="field">
              <label className="label" htmlFor="timing">
                사용 시기
              </label>
              <Select id="timing" value={timing} options={TIMINGS} onChange={setTiming} />
            </div>
          </div>
          <p className="caption">국내 의약품은 제품명으로, WADA 금지목록 성분은 영문 성분명으로도 찾을 수 있어요(예: letrozole, meldonium).</p>
          <button className="btn btn-block" disabled={!query.trim()}>
            확인 절차 보기 <ArrowRight size={18} />
          </button>
          {error && <p className="error">{error}</p>}
        </form>

        <div className="span-7">
          {!result ? (
            <div className="empty">
              <Pill size={28} style={{ marginBottom: 8 }} />
              <p>제품명이나 성분명을 입력하면 확인 절차를 보여드려요.</p>
            </div>
          ) : (
            <section className="card" aria-live="polite" data-figure="check-result">
              <div className="stack">
                <p className="caption">
                  “{result.query}” · {result.list_version} 금지목록 기준
                </p>
                <StatusBadge status={result.status} />
              </div>


              {result.supplement_warning && (
                <div className="notice notice-caution">
                  <TriangleAlert size={18} />
                  <span>보충제는 성분표에 없는 금지물질이 섞여 있을 수 있어요. 성분과 관계없이 주의가 필요해요.</span>
                </div>
              )}

              {result.ingredients.length > 0 && (
                <div>
                  <p className="label" style={{ marginBottom: 6 }}>
                    {result.matched_kind === "category"
                      ? "이 제품군에서 주의할 성분"
                      : result.matched_kind === "unmatched"
                        ? "이름이 비슷한 성분 — 같은 성분인지 포장의 성분명으로 확인하세요"
                        : "성분"}
                  </p>
                  {result.ingredients.map((i) => (
                    <div key={i.name_en} className="ingredient">
                      <strong>
                        {i.name_ko}
                        {showCodes && i.wada_class && <span className="caption"> · {i.wada_class}</span>}
                      </strong>
                      {result.matched_kind !== "substance" && <StatusBadge status={i.status} small />}
                      {i.note && <span className="caption">{i.note}</span>}
                      {(result.matched_kind === "category" || result.matched_kind === "unmatched") && (
                        <button
                          type="button"
                          className="btn-sub small"
                          style={{ alignSelf: "flex-start" }}
                          onClick={() => {
                            setQuery(i.name_ko);
                            run(i.name_ko);
                          }}
                        >
                          이 성분으로 확인
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {result.candidates.length > 0 && (
                <div className="stack" style={{ gap: 6 }} data-test="candidates">
                  <p className="label">같은 이름의 제품이 여러 개예요. 성분이 달라 하나로 판단하지 않았어요</p>
                  <p className="caption">갖고 있는 제품의 정확한 이름을 골라 다시 확인하세요.</p>
                  {result.candidates.map((c) => (
                    <div key={c.name} className="ingredient">
                      <strong>{c.name}</strong>
                      <span className="caption">
                        {c.otc} · {c.ingredients.join(", ")}
                      </span>
                      <button
                        type="button"
                        className="btn-sub small"
                        style={{ alignSelf: "flex-start" }}
                        onClick={() => {
                          setQuery(c.name);
                          run(c.name);
                        }}
                      >
                        이 제품으로 확인
                      </button>
                    </div>
                  ))}
                </div>
              )}

              <div className="stack">
                <p className="label">확인 절차</p>
                <ol className="steps">
                  {result.steps.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ol>
              </div>

              <div className="row wrap">
                <button type="button" className="btn-sub" onClick={() => navigate("/learn", { state: { check: result } })}>
                  <MessageCircle size={16} /> AI에게 더 묻기
                </button>
              </div>
              {result.data_sources.length > 0 && (
                <p className="caption">
                  제품·성분 정보:{" "}
                  {result.data_sources.map((d, i) => (
                    <span key={d.url}>
                      {i > 0 && " · "}
                      <a href={d.url} target="_blank" rel="noreferrer">
                        {d.label}
                      </a>
                    </span>
                  ))}
                </p>
              )}
            </section>
          )}
        </div>
      </div>
    </>
  );
}
