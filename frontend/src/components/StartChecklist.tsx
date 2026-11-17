import { ArrowRight, Circle, CircleCheck, ListChecks } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router";
import { api, type StartChecklist as Checklist } from "../api";

/** 관리자 시작 체크리스트. 끝났는지는 서버가 실제 데이터로 정한다. reloadKey가 바뀌면(선수 등록 등) 다시 불러온다. */
export function StartChecklist({ reloadKey }: { reloadKey: unknown }) {
  const [data, setData] = useState<Checklist | null>(null);

  useEffect(() => {
    api.checklist().then(setData, () => setData(null));
  }, [reloadKey]);

  if (!data) return null;
  const setHidden = (hidden: boolean) => api.setChecklist(hidden).then(() => setData({ ...data, hidden }));

  if (data.hidden)
    return (
      <button className="chip chip-plain" style={{ marginBottom: 16 }} onClick={() => setHidden(false)}>
        <ListChecks size={14} /> 시작 체크리스트 보기
      </button>
    );

  const done = data.items.filter((i) => i.done).length;
  return (
    <section className="card stack checklist" style={{ marginBottom: 24 }}>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
        <h2 className="heading">
          시작 체크리스트 <span className="muted">{done}/{data.items.length}</span>
        </h2>
        <button className="onboarding-skip" onClick={() => setHidden(true)}>
          숨기기
        </button>
      </div>
      <p className="caption">{done === data.items.length ? "모두 끝났어요. 이제 선수들이 교육을 들을 수 있어요." : "위에서부터 차례로 하면 돼요."}</p>
      <ol className="checklist-items">
        {data.items.map((item) => (
          <li key={item.key} className={item.done ? "done" : undefined}>
            <Link to={item.link}>
              {item.done ? <CircleCheck size={18} /> : <Circle size={18} />}
              <span className="checklist-text">
                <strong>{item.label}</strong>
                <span className="caption">{item.detail}</span>
              </span>
              <ArrowRight size={16} />
            </Link>
          </li>
        ))}
      </ol>
    </section>
  );
}
