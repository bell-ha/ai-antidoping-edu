import { FlaskConical } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type ComputeRequest, type DemoScenario, type DemoScenarios } from "../api";
import { Select } from "./Select";

// 데모 전용 테스트 시나리오 (시범 서버에서는 /api/demo/examples가 404라 나타나지 않는다).
// 논문 Figure(data-figure)를 가리지 않도록 입력 폼 밖, 접힌 상태로 둔다.

const MODEL_LABEL = { synthetic_trend: "합성 추세 모델(시연용)", rnn: "연구진 RNN" } as const;
const WARNING_LABEL = { ratio: "인상·용상 비율", jump: "직전 대비 급변" } as const;

export function ScenarioPanel({ onLoad }: { onLoad: (req: ComputeRequest, scenario: DemoScenario) => void }) {
  const [data, setData] = useState<DemoScenarios | null>(null);
  const [id, setId] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api.demoScenarios().then(
      (d) => {
        setData(d);
        setId(d.scenarios[0]?.id ?? "");
      },
      () => setData(null),
    );
  }, []);

  if (!data || data.scenarios.length === 0) return null;
  const s = data.scenarios.find((x) => x.id === id);

  const load = () => {
    if (!s) return;
    setError("");
    api.demoExample(s.id).then((req) => onLoad(req, s), (e) => setError(e.message));
  };

  return (
    <details className="card test-panel" data-test="scenarios">
      <summary className="row">
        <FlaskConical size={18} />
        <strong>테스트 시나리오</strong>
        <span className="caption">데모 전용 · 예측 방식: {MODEL_LABEL[data.model]}</span>
      </summary>
      <div className="stack">
        <div className="row wrap" style={{ alignItems: "flex-end" }}>
          <div className="field" style={{ flex: "1 1 260px" }}>
            <label className="label" htmlFor="scenario">
              시나리오
            </label>
            <Select id="scenario" value={id} options={data.scenarios.map((x) => ({ value: x.id, label: `${x.id} · ${x.label}` }))} onChange={setId} />
          </div>
          <button type="button" className="btn-sub" onClick={load}>
            입력란에 불러오기
          </button>
        </div>
        {s && (
          <div className="stack" style={{ gap: 6 }}>
            <p className="muted">{s.description}</p>
            <div className="row wrap">
              <span className="caption">기대 태그</span>
              {s.expect_labels.map((l) => (
                <span key={l} className="chip">
                  {l}
                </span>
              ))}
            </div>
            {s.warnings.length > 0 && <p className="caption">먼저 입력 확인 경고가 떠야 함: {s.warnings.map((w) => WARNING_LABEL[w]).join(", ")} → “확인했어요” 후 계산</p>}
          </div>
        )}
        {error && <p className="error">{error}</p>}
      </div>
    </details>
  );
}
