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
    <div className="app">
      <main className="main no-tabs" style={{ paddingTop: 32 }}>
        <section className="surface">
          <div className="stack">
            <h1 className="title">AI 반도핑 교육</h1>
            <p className="sub">경기력 변화에 맞춘 도핑 예방교육과 약물 확인을 도와드려요.</p>
          </div>
          <form className="stack" onSubmit={submit}>
            <label className="label" htmlFor="code">
              접근 코드
            </label>
            <input
              id="code"
              className="input"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              autoComplete="off"
              placeholder="연구진에게 받은 코드"
            />
            {error && <p className="error">{error}</p>}
            <button className="btn btn-block" disabled={!code.trim()}>
              시작하기 <ArrowRight size={18} />
            </button>
          </form>
        </section>

        {personas.length > 0 && (
          <section className="surface">
            <h2 className="heading">데모로 둘러보기</h2>
            <div className="stack">
              {personas.map((p) => (
                <button key={p.code} className="card-link" onClick={() => login(p.code)}>
                  <strong>{p.info.label}</strong>
                  <span className="sub">{p.description}</span>
                </button>
              ))}
            </div>
          </section>
        )}
        <p className="footnote">{personas.length > 0 && "합성 데이터 · "}연구용 프로토타입 · 최종 확인은 KADA</p>
      </main>
    </div>
  );
}
