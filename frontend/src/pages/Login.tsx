import { ArrowRight, Search, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { api, ApiError, type DemoCode, type SessionInfo } from "../api";

export function Login({ onLogin }: { onLogin: (who: SessionInfo) => void }) {
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [codes, setCodes] = useState<DemoCode[]>([]);
  const [filter, setFilter] = useState("");
  const [tier, setTier] = useState<number | null>(null);

  useEffect(() => {
    api.demoCodes().then(setCodes, () => setCodes([]));
  }, []);

  const login = (value: string) => {
    setError("");
    api.login(value).then(onLogin, (e) => setError(e instanceof ApiError ? e.message : "다시 시도해 주세요."));
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (code.trim()) login(code.trim());
  };

  const admins = codes.filter((c) => c.role === "admin");
  const tiers = [...new Set(codes.map((c) => c.tier).filter((t): t is number => t !== null))].sort((a, b) => b - a);
  const athletes = useMemo(
    () =>
      codes
        .filter((c) => c.role === "athlete")
        .filter((c) => tier === null || c.tier === tier)
        .filter((c) => !filter.trim() || c.name.includes(filter.trim()) || c.number.toLowerCase().includes(filter.trim().toLowerCase())),
    [codes, filter, tier],
  );

  return (
    <>
      <header className="nav">
        <div className="container nav-inner">
          <span className="brand">AI 반도핑 교육</span>
        </div>
      </header>

      <main className="container main">
        <div className="grid">
          <section className="span-6 stack-lg">
            <div className="stack">
              <h1 className="display">AI 반도핑 교육</h1>
              <p className="muted">
                WADA·KADA 자료로 만든 도핑방지 교육 300개와 퀴즈, 약 이름으로 물어볼 수 있는 질문하기를 제공합니다. 일주일에 한 번 들어와
                이번 주 교육을 들어 주세요.
              </p>
            </div>
            <form className="card" onSubmit={submit}>
              <div className="field">
                <label className="label" htmlFor="code">
                  로그인 코드
                </label>
                <input
                  id="code"
                  className="input"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  autoComplete="off"
                  placeholder="관리자에게 받은 코드 (예: WL-001-abcd2345)"
                />
              </div>
              {error && <p className="error">{error}</p>}
              <button className="btn btn-block" disabled={!code.trim()}>
                로그인 <ArrowRight size={18} />
              </button>
            </form>
          </section>

          {codes.length > 0 && (
            <section className="span-6 stack">
              <div className="stack" style={{ gap: 4 }}>
                <h2 className="heading">데모 코드</h2>
                <p className="caption">누르면 바로 그 계정으로 들어가요. 데모에서만 보이는 목록입니다.</p>
              </div>

              {admins.map((a) => (
                <button key={a.code} className="demo-code demo-code-admin" onClick={() => login(a.code)}>
                  <ShieldCheck size={18} />
                  <span className="demo-code-name">{a.name}</span>
                  <code>{a.code}</code>
                </button>
              ))}

              <div className="row wrap" style={{ gap: 8 }}>
                <div className="demo-search">
                  <Search size={16} />
                  <input className="input" value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="이름·번호 찾기" aria-label="선수 찾기" />
                </div>
                <button className={`chip ${tier === null ? "chip-on" : "chip-plain"}`} onClick={() => setTier(null)}>
                  전체
                </button>
                {tiers.map((t) => (
                  <button key={t} className={`chip ${tier === t ? "chip-on" : "chip-plain"}`} onClick={() => setTier(t)}>
                    {t}단계
                  </button>
                ))}
              </div>

              <div className="demo-list" role="list" aria-label="선수 데모 코드">
                {athletes.map((a) => (
                  <button key={a.code} role="listitem" className="demo-code" onClick={() => login(a.code)}>
                    <span className="demo-code-num">{a.number}</span>
                    <span className="demo-code-name">{a.name}</span>
                    {a.tier !== null && <span className="tier-badge">{a.tier}단계</span>}
                    <code>{a.code}</code>
                  </button>
                ))}
                {athletes.length === 0 && <p className="caption">맞는 선수가 없어요.</p>}
              </div>
            </section>
          )}
        </div>
      </main>

      <footer className="footer">
        <p className="container caption">{codes.length > 0 && "더미 데이터 · "}연구용 프로토타입</p>
      </footer>
    </>
  );
}
