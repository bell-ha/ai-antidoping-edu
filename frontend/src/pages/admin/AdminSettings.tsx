import { Minus, Plus, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Overview, type TierSetting } from "../../api";
import { Help } from "../../components/Help";

export function AdminSettings() {
  const [data, setData] = useState<Overview | null>(null);
  const [tiers, setTiers] = useState<TierSetting[]>([]);
  const [msg, setMsg] = useState("");
  const [rerunMsg, setRerunMsg] = useState("");
  const [error, setError] = useState("");
  const dirty = !!data && JSON.stringify(tiers) !== JSON.stringify(data.settings.tiers);
  // 저장하지 않고 창을 닫거나 새로고침하면 묻는다(값이 말없이 사라지던 문제, 테스터 1·2·3·4)
  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const apply = (o: Overview) => {
    setData(o);
    setTiers(o.settings.tiers);
  };
  useEffect(() => {
    api.overview().then(apply, (e) => setError(e.message));
  }, []);

  if (error && !data) return <p className="error">{error}</p>;
  if (!data) return null;

  const set = (i: number, patch: Partial<TierSetting>) => {
    setMsg("");
    setTiers(tiers.map((t, j) => (j === i ? { ...t, ...patch } : t)));
  };
  // 빈 칸은 0으로 바꾸지 않고 비워 둔 채 저장을 막는다
  const num = (v: string) => (v === "" ? Number.NaN : Number(v));
  const empty = tiers.some((t) => [t.lessons_per_week, t.quiz_probability, t.quiz_questions].some((x) => Number.isNaN(x)));
  // 높은 단계일수록 양이 같거나 많아야 한다(설계: 단계가 높을수록 교육·퀴즈가 많음). 막지는 않고 알린다
  const notIncreasing = tiers.slice(1).some((t, i) => t.lessons_per_week < tiers[i].lessons_per_week || t.quiz_probability < tiers[i].quiz_probability);
  const n = data.athletes.length;
  const addTier = () => {
    const top = tiers[tiers.length - 1];
    setMsg("");
    setTiers([...tiers, { tier: tiers.length + 1, lessons_per_week: top.lessons_per_week + 3, quiz_probability: Math.min(1, Math.round((top.quiz_probability + 0.15) * 100) / 100), quiz_questions: top.quiz_questions }]);
  };
  const save = () => {
    setError("");
    if (empty) return setError("빈 칸이 있어요. 모든 칸에 숫자를 넣어 주세요.");
    api.saveSettings({ tiers: tiers.map((t, i) => ({ ...t, tier: i + 1 })) }).then(
      (o) => {
        apply(o);
        setMsg("저장하고 단계를 다시 나눴어요.");
      },
      (e) => setError(e.message),
    );
  };

  return (
    <>
      <div className="page-head">
        <h1 className="title">단계 설정</h1>
        <p className="muted">
          선수 {n}명을 모델의 실제−예측이 큰 순서로 세워 단계 수만큼 인원을 고르게 나눠요. 결과가 없는 선수(대회 기록 3개 미만)는 교육이 가장 적은
          단계예요. 단계가 높을수록 한 주에 듣는 교육과 깜짝 퀴즈가 많아요. 모든 단계가 같은 주제 순서(대분류를 돌아가며)로 배우고 양만 달라요. 바꾼 개수는 다음 주(월)부터 적용돼요.
        </p>
      </div>

      <div className="card stack">
        <div className="table-scroll">
          <table className="data-table settings-table">
            <thead>
              <tr>
                <th>단계</th>
                <th className="num">인원(지금 기준)</th>
                <th>
                  주당 교육 수
                  <Help label="주당 교육 수" text="한 주(월~일)에 새로 정해지는 교육 개수예요. 지난주에 못 들은 교육은 이번 주 목록에 남아요." />
                </th>
                <th>
                  깜짝 퀴즈 확률(하루 첫 접속)
                  <Help label="깜짝 퀴즈 확률" text="선수가 그날 처음 들어올 때 퀴즈가 나올 확률이에요. 이미 배운 교육에서만 나오고, 전에 틀린 문제가 먼저 나와요." />
                </th>
                <th>
                  한 번에 문항 수
                  <Help label="한 번에 문항 수" text="깜짝 퀴즈가 나올 때 한 번에 푸는 문제 수예요." />
                </th>
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
                      {i === 0 && <span className="caption"> 교육 가장 적음</span>}
                      {i === tiers.length - 1 && i > 0 && <span className="caption"> 교육 가장 많음</span>}
                    </td>
                    <td className="num" data-label="인원">{Math.floor(((i + 1) * n) / tiers.length) - Math.floor((i * n) / tiers.length)}명</td>
                    <td data-label="주당 교육 수">
                      <input className="input input-sm" type="number" min={0} max={50} value={Number.isNaN(t.lessons_per_week) ? "" : t.lessons_per_week}
                        onChange={(e) => set(i, { lessons_per_week: num(e.target.value) })} aria-label={`${i + 1}단계 주당 교육 수`} />
                    </td>
                    <td data-label="깜짝 퀴즈 확률">
                      <input className="input input-sm" type="number" min={0} max={100} step={5} value={Number.isNaN(t.quiz_probability) ? "" : Math.round(t.quiz_probability * 100)}
                        onChange={(e) => set(i, { quiz_probability: num(e.target.value) / 100 })} aria-label={`${i + 1}단계 퀴즈 확률`} /> %
                    </td>
                    <td data-label="한 번에 문항 수">
                      <input className="input input-sm" type="number" min={1} max={10} value={Number.isNaN(t.quiz_questions) ? "" : t.quiz_questions}
                        onChange={(e) => set(i, { quiz_questions: num(e.target.value) })} aria-label={`${i + 1}단계 문항 수`} />
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        <div className="row wrap" style={{ gap: 8 }}>
          <button className="btn-sub" disabled={tiers.length >= 10}
            onClick={addTier}>
            <Plus size={14} /> 단계 추가
          </button>
          <button className="btn-sub" disabled={tiers.length <= 1} onClick={() => setTiers(tiers.slice(0, -1))}>
            <Minus size={14} /> 가장 높은 단계 빼기
          </button>
          <button className="btn" style={{ height: 40, marginLeft: "auto" }} onClick={save}>
            저장하고 단계 다시 나누기
          </button>
        </div>
        {dirty && <p className="caption">저장하지 않은 변경이 있어요.</p>}
        {notIncreasing && <p className="caption">높은 단계의 주당 교육 수나 퀴즈 확률이 아래 단계보다 적어요. 의도한 게 맞는지 확인해 주세요.</p>}
        {msg && <p className="caption">{msg}</p>}
        {error && <p className="error">{error}</p>}
      </div>

      <div className="card stack" style={{ marginTop: 24 }}>
        <h2 className="heading">모델 다시 돌리기</h2>
        <p className="muted">
          지금 모델: {data.model_label}. 연구진 모델 파일을 바꿨다면 모든 선수의 결과를 다시 계산하고 단계를 다시 나눠요.
        </p>
        <button className="btn-sub" style={{ alignSelf: "flex-start" }}
          onClick={() => window.confirm("모든 선수의 모델 결과를 다시 계산하고 단계를 다시 나눌까요?") &&
            api.rerank().then((o) => { apply(o); setRerunMsg(`모든 선수를 다시 계산했어요(${new Date().toLocaleTimeString("ko-KR")}).`); }, (e) => setError(e.message))}>
          <RefreshCw size={14} /> 전체 다시 계산
        </button>
        {rerunMsg && <p className="caption">{rerunMsg}</p>}
      </div>
    </>
  );
}
