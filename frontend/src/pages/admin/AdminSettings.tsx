import { Minus, Plus, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Overview, type TierSetting } from "../../api";

export function AdminSettings() {
  const [data, setData] = useState<Overview | null>(null);
  const [tiers, setTiers] = useState<TierSetting[]>([]);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const apply = (o: Overview) => {
    setData(o);
    setTiers(o.settings.tiers);
  };
  useEffect(() => {
    api.overview().then(apply, (e) => setError(e.message));
  }, []);

  if (error && !data) return <p className="error">{error}</p>;
  if (!data) return null;

  const set = (i: number, patch: Partial<TierSetting>) => setTiers(tiers.map((t, j) => (j === i ? { ...t, ...patch } : t)));
  const n = data.athletes.length;
  const save = () => {
    setError("");
    api.saveSettings({ tiers: tiers.map((t, i) => ({ ...t, tier: i + 1 })) }).then(
      (o) => {
        apply(o);
        setMsg("저장하고 다시 줄 세웠어요.");
      },
      (e) => setError(e.message),
    );
  };

  return (
    <>
      <div className="page-head">
        <h1 className="title">단계 설정</h1>
        <p className="muted">
          선수 {n}명을 모델의 관측−예측이 큰 순서로 줄 세워 단계 수만큼 고르게 나눠요. 결과가 없는 선수(기록 부족)는 가장 낮은 단계예요. 단계가 높을수록
          한 주에 듣는 교육과 갑자기 퀴즈가 많아요.
        </p>
      </div>

      <div className="card stack">
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>단계</th>
                <th className="num">인원(예상)</th>
                <th>주당 교육 수</th>
                <th>갑자기 퀴즈 확률(하루 첫 접속)</th>
                <th>한 번에 문항 수</th>
              </tr>
            </thead>
            <tbody>
              {tiers
                .map((t, i) => ({ t, i }))
                .reverse()
                .map(({ t, i }) => (
                  <tr key={i}>
                    <td>
                      <span className="tier-badge">{i + 1}단계</span>
                      {i === 0 && <span className="caption"> 가장 낮음</span>}
                      {i === tiers.length - 1 && i > 0 && <span className="caption"> 가장 높음</span>}
                    </td>
                    <td className="num">{Math.floor(((i + 1) * n) / tiers.length) - Math.floor((i * n) / tiers.length)}명</td>
                    <td>
                      <input className="input input-sm" type="number" min={0} max={50} value={t.lessons_per_week}
                        onChange={(e) => set(i, { lessons_per_week: Number(e.target.value) })} aria-label={`${i + 1}단계 주당 교육 수`} />
                    </td>
                    <td>
                      <input className="input input-sm" type="number" min={0} max={100} step={5} value={Math.round(t.quiz_probability * 100)}
                        onChange={(e) => set(i, { quiz_probability: Number(e.target.value) / 100 })} aria-label={`${i + 1}단계 퀴즈 확률`} /> %
                    </td>
                    <td>
                      <input className="input input-sm" type="number" min={1} max={10} value={t.quiz_questions}
                        onChange={(e) => set(i, { quiz_questions: Number(e.target.value) })} aria-label={`${i + 1}단계 문항 수`} />
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        <div className="row wrap" style={{ gap: 8 }}>
          <button className="btn-sub" disabled={tiers.length >= 10}
            onClick={() => setTiers([...tiers, { ...tiers[tiers.length - 1], tier: tiers.length + 1 }])}>
            <Plus size={14} /> 단계 추가
          </button>
          <button className="btn-sub" disabled={tiers.length <= 1} onClick={() => setTiers(tiers.slice(0, -1))}>
            <Minus size={14} /> 맨 위 단계 빼기
          </button>
          <button className="btn" style={{ height: 40, marginLeft: "auto" }} onClick={save}>
            저장하고 다시 줄 세우기
          </button>
        </div>
        {msg && <p className="caption">{msg}</p>}
        {error && <p className="error">{error}</p>}
      </div>

      <div className="card stack" style={{ marginTop: 24 }}>
        <h2 className="heading">모델 다시 돌리기</h2>
        <p className="muted">
          지금 모델: {data.model_version}. 연구진 모델 파일을 바꿨다면 모든 선수의 결과를 다시 계산하고 줄을 다시 세워요.
        </p>
        <button className="btn-sub" style={{ alignSelf: "flex-start" }}
          onClick={() => api.rerank().then((o) => { apply(o); setMsg("모든 선수를 다시 계산했어요."); }, (e) => setError(e.message))}>
          <RefreshCw size={14} /> 전체 다시 계산
        </button>
      </div>
    </>
  );
}
