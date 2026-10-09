import { ArrowRight } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError, type DemoPersona, type SessionInfo } from "../api";

export function Start({ onLogin }: { onLogin: (who: SessionInfo) => void }) {
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [personas, setPersonas] = useState<DemoPersona[]>([]);

  useEffect(() => {
    api.personas().then(setPersonas, () => setPersonas([]));
  }, []);

  const login = (value: string) => {
    setError("");
    api.login(value).then(onLogin, (e) => setError(e instanceof ApiError ? e.message : "다시 시도해 주세요."));
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (code.trim()) login(code.trim());
  };

  return (
    <>
      <header className="nav">
        <div className="container nav-inner">
          <span className="brand">AI 반도핑 교육</span>
        </div>
      </header>

      <main className="container main">
        <div className="grid">
          <section className={`stack-lg ${personas.length ? "span-6" : "span-6"}`}>
            <div className="stack">
              <h1 className="display">AI 반도핑 교육</h1>
              <p className="muted">
                경기력 변화에 맞춘 도핑 예방교육, 약물·보충제 확인 절차, 공식 자료에 근거한 질의응답을 한곳에서 제공합니다.
              </p>
            </div>
            <form className="card" onSubmit={submit}>
              <div className="field">
                <label className="label" htmlFor="code">
                  접근 코드
                </label>
                <input id="code" className="input" value={code} onChange={(e) => setCode(e.target.value)} autoComplete="off" placeholder="연구진에게 받은 코드" />
              </div>
              {error && <p className="error">{error}</p>}
              <button className="btn btn-block" disabled={!code.trim()}>
                시작하기 <ArrowRight size={18} />
              </button>
            </form>
          </section>

          {personas.length > 0 && (
            <section className="span-6 stack-lg">
              <div className="stack">
                <h2 className="heading">데모로 둘러보기</h2>
                <p className="caption">합성 데이터로 만든 예시 사용자입니다.</p>
              </div>
              <div className="cards-2">
                {personas.map((p) => (
                  <button key={p.code} className="card-soft" onClick={() => login(p.code)}>
                    <strong>{p.info.label}</strong>
                    <span className="muted" style={{ fontSize: "var(--fs-label)" }}>
                      {p.description}
                    </span>
                  </button>
                ))}
              </div>
            </section>
          )}
        </div>
      </main>

      <footer className="footer">
        <p className="container caption">{personas.length > 0 && "합성 데이터 · "}연구용 프로토타입 · 최종 확인은 KADA</p>
      </footer>
    </>
  );
}
