import { Download, Plus, Search } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router";
import { api, type IssuedCode, type Overview } from "../../api";
import { CodeHandoff } from "../../components/CodeHandoff";
import { Dialog } from "../../components/Dialog";
import { Help } from "../../components/Help";
import { StartChecklist } from "../../components/StartChecklist";
import { weightClassLabel } from "../../session";

type SortKey = "rank" | "number" | "lessons" | "quiz" | "questions" | "visit";

export function AdminAthletes() {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  const [tier, setTier] = useState<number | null>(null);
  const [filter, setFilter] = useState("");
  const [sort, setSort] = useState<SortKey>("rank");
  const [adding, setAdding] = useState(false);

  const load = () => api.overview().then(setData, (e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);

  const rows = useMemo(() => {
    if (!data) return [];
    const by: Record<SortKey, (a: Overview["athletes"][number]) => number | string> = {
      rank: (a) => a.rank ?? 1e9,
      number: (a) => a.number,
      lessons: (a) => -a.lessons_completed,
      quiz: (a) => -(a.quiz_correct + a.quiz_wrong),
      questions: (a) => -a.questions,
      visit: (a) => (a.last_visit ? -Date.parse(a.last_visit) : 0),
    };
    return data.athletes
      .filter((a) => tier === null || a.tier === tier)
      .filter((a) => !filter.trim() || a.name.includes(filter.trim()) || a.number.toLowerCase().includes(filter.trim().toLowerCase()))
      .sort((x, y) => (by[sort](x) < by[sort](y) ? -1 : by[sort](x) > by[sort](y) ? 1 : 0));
  }, [data, tier, filter, sort]);

  if (error) return <p className="error">{error}</p>;
  if (!data) return null;

  const counts = data.settings.tiers.map((t) => data.athletes.filter((a) => a.tier === t.tier).length);
  const th = (key: SortKey, label: string, num = false) => (
    <th className={num ? "num" : undefined}>
      <button className={`th-sort${sort === key ? " on" : ""}`} onClick={() => setSort(key)}>
        {label}
      </button>
    </th>
  );

  return (
    <>
      <div className="page-head page-head-row">
        <div className="stack" style={{ gap: 4 }}>
          <h1 className="title">선수 관리</h1>
          <p className="muted">
            선수 {data.athletes.length}명 · 모델 {data.model_version} · 단계는 모델의 관측−예측이 큰 순서(예측보다 기록이 많이 오른 순)로 나눠요.
          </p>
        </div>
        <button className="btn" style={{ height: 40 }} onClick={() => setAdding(true)}>
          <Plus size={16} /> 선수 등록
        </button>
      </div>

      <StartChecklist reloadKey={data} />

      <div className="row wrap" style={{ gap: 8, marginBottom: 16 }}>
        <button className={`chip ${tier === null ? "chip-on" : "chip-plain"}`} onClick={() => setTier(null)}>
          전체 {data.athletes.length}
        </button>
        {[...data.settings.tiers].reverse().map((t) => (
          <button key={t.tier} className={`chip ${tier === t.tier ? "chip-on" : "chip-plain"}`} onClick={() => setTier(t.tier)}>
            {t.tier}단계 {counts[t.tier - 1]} · 주 {t.lessons_per_week}개
          </button>
        ))}
        <div className="demo-search" style={{ marginLeft: "auto" }}>
          <Search size={16} />
          <input className="input" value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="이름·번호 찾기" aria-label="선수 찾기" />
        </div>
      </div>

      <div className="export-menu" style={{ marginBottom: 16 }}>
        <span className="caption">CSV 내보내기(엑셀에서 열림)</span>
        {(
          [
            ["athletes", "선수별 요약"],
            ["quizzes", "퀴즈 풀이"],
            ["lessons", "교육 이수"],
            ["chats", "질문과 답"],
            ["records", "경기 기록"],
          ] as const
        ).map(([kind, label]) => (
          <a key={kind} className="btn-sub small" href={`/api/admin/export/${kind}.csv`} download>
            <Download size={14} /> {label}
          </a>
        ))}
      </div>

      <div className="table-scroll card" style={{ padding: 0 }}>
        <table className="data-table">
          <thead>
            <tr>
              {th("rank", "순위", true)}
              <th>
                단계
                <Help label="단계" text="모델의 관측−예측이 큰 선수부터 줄 세워 단계 수만큼 고르게 나눠요. 높은 단계일수록 주당 교육과 갑자기 퀴즈가 많아요. 결과가 없는 선수는 가장 낮은 단계예요. 도핑 여부를 판단하는 점수가 아니에요." />
              </th>
              {th("number", "번호")}
              <th>이름</th>
              <th>체급</th>
              <th className="num">
                관측−예측
                <Help label="관측−예측" text="마지막 대회 합계(관측)에서 연구진 모델이 그 전 기록으로 예측한 합계를 뺀 값(kg)이에요. +면 예측보다 더 들었다는 뜻이에요. 기록이 2개 미만이면 결과가 없어요." />
              </th>
              <th className="num">기록</th>
              {th("lessons", "이수", true)}
              {th("quiz", "퀴즈 정답/오답", true)}
              <th className="num">오답 남음</th>
              {th("questions", "질문", true)}
              {th("visit", "마지막 접속일")}
            </tr>
          </thead>
          <tbody>
            {data.athletes.length === 0 && (
              <tr>
                <td colSpan={12}>
                  <div className="empty-state">
                    <strong>아직 등록된 선수가 없어요</strong>
                    <span className="muted">선수를 등록하면 로그인 코드가 나오고, 경기 기록을 넣으면 단계가 정해져요.</span>
                    <button className="btn" onClick={() => setAdding(true)}>
                      <Plus size={16} /> 첫 선수 등록하기
                    </button>
                  </div>
                </td>
              </tr>
            )}
            {rows.map((a) => (
              <tr key={a.id}>
                <td className="num">{a.rank ?? "—"}</td>
                <td>{a.tier !== null && <span className="tier-badge">{a.tier}단계</span>}</td>
                <td>
                  <Link to={`/admin/athletes/${a.id}`}>{a.number}</Link>
                </td>
                <td>
                  <Link to={`/admin/athletes/${a.id}`}>{a.name}</Link>
                </td>
                <td>{weightClassLabel(a.weight_class)}</td>
                <td className="num">{a.residual === null ? <span className="caption">결과 없음</span> : `${a.residual > 0 ? "+" : ""}${a.residual}kg`}</td>
                <td className="num">{a.records}</td>
                <td className="num">{a.lessons_completed}</td>
                <td className="num">
                  {a.quiz_correct}/{a.quiz_wrong}
                </td>
                <td className="num">{a.wrong_open}</td>
                <td className="num">{a.questions}</td>
                <td>{a.last_visit ? a.last_visit.slice(0, 10) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {adding && <AddAthlete onClose={() => setAdding(false)} onDone={load} />}
    </>
  );
}

function AddAthlete({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [name, setName] = useState("");
  const [birth, setBirth] = useState("2005");
  const [issued, setIssued] = useState<IssuedCode | null>(null);
  const [error, setError] = useState("");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    api.createAthlete(name.trim(), Number(birth)).then(
      (r) => {
        setIssued(r);
        onDone();
      },
      (e) => setError(e.message),
    );
  };

  return (
    <Dialog onClose={onClose}>
      {issued ? (
        <>
          <h2 className="heading">
            {name.trim()} ({issued.number}) 등록 완료
          </h2>
          <p className="muted">로그인 코드는 지금만 볼 수 있어요(서버에 원문이 남지 않음). 복사하거나 안내문을 그대로 보내 주세요. 잃어버리면 선수 상세에서 다시 발급해요.</p>
          <CodeHandoff name={name.trim()} code={issued.code} />
          <button className="btn" onClick={onClose}>
            닫기
          </button>
        </>
      ) : (
        <form className="stack" onSubmit={submit}>
          <h2 className="heading">선수 등록 (남자 역도)</h2>
          <div className="field">
            <label className="label" htmlFor="name">
              이름
            </label>
            <input id="name" className="input" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="field">
            <label className="label" htmlFor="birth">
              출생연도
            </label>
            <input id="birth" className="input" inputMode="numeric" value={birth} onChange={(e) => setBirth(e.target.value)} />
          </div>
          {error && <p className="error">{error}</p>}
          <button className="btn" disabled={!name.trim() || !/^\d{4}$/.test(birth)}>
            등록하고 코드 받기
          </button>
        </form>
      )}
    </Dialog>
  );
}
