import { ArrowRight, ExternalLink, MessageCircle, TriangleAlert } from "lucide-react";
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
      <section className="surface">
        <h1 className="heading">AI 약물 확인</h1>
        <form className="stack" style={{ gap: 16 }} onSubmit={submit}>
          <div className="field">
            <label className="label" htmlFor="q">
              제품명 또는 성분명
            </label>
            <input id="q" className="input" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="예: 감기약, 슈도에페드린" autoComplete="off" />
          </div>
          <div className="grid-2">
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
          <button className="btn btn-block" disabled={!query.trim()}>
            확인 절차 보기 <ArrowRight size={18} />
          </button>
          {error && <p className="error">{error}</p>}
        </form>
      </section>

      {result && (
        <section className="surface" aria-live="polite">
          <div className="stack">
            <p className="caption">
              “{result.query}” · {result.list_version} 금지목록 기준
            </p>
            <StatusBadge status={result.status} />
          </div>

          {result.ingredients.length > 0 && (
            <div className="box">
              <p className="label" style={{ marginBottom: 8 }}>
                {result.matched_kind === "category" ? "이 제품군에서 주의할 성분" : "성분"}
              </p>
              {result.ingredients.map((i) => (
                <div key={i.name_en} className="ingredient">
                  <div className="stack" style={{ gap: 2 }}>
                    <strong>
                      {i.name_ko}
                      {showCodes && i.wada_class && <span className="caption"> · {i.wada_class}</span>}
                    </strong>
                    {result.matched_kind !== "substance" && <StatusBadge status={i.status} small />}
                    {i.note && <span className="caption">{i.note}</span>}
                    {result.matched_kind === "category" && (
                      <button className="btn-sub" style={{ alignSelf: "flex-start", height: 32, marginTop: 4 }} onClick={() => { setQuery(i.name_ko); run(i.name_ko); }}>
                        이 성분으로 확인
                      </button>
                    )}
                  </div>
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

          {result.supplement_warning && (
            <div className="notice notice-caution">
              <TriangleAlert size={18} />
              <span>보충제는 성분표에 없는 금지물질이 섞여 있을 수 있어요. 성분과 관계없이 주의가 필요해요.</span>
            </div>
          )}

          <div className="row wrap">
            {result.links.map((l) => (
              <a key={l.url} className="btn-sub" href={l.url} target="_blank" rel="noreferrer">
                {l.label} <ExternalLink size={14} />
              </a>
            ))}
            <button className="btn-sub" onClick={() => navigate("/learn", { state: { check: result } })}>
              <MessageCircle size={16} /> AI에게 더 묻기
            </button>
          </div>

          <p className="caption">이 결과는 참고용입니다. 복용 전 반드시 KADA 의약품 검색 또는 팀 닥터에게 확인하세요.</p>
        </section>
      )}
    </>
  );
}
