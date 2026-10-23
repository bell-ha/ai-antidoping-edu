import { Download, Plus, Search } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router";
import { api, type IssuedCode, type Overview } from "../../api";
import { Dialog } from "../../components/Dialog";
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
              <th>단계</th>
              {th("number", "번호")}
              <th>이름</th>
              <th>체급</th>
              <th className="num">관측−예측</th>
              <th className="num">기록</th>
              {th("lessons", "이수", true)}
              {th("quiz", "퀴즈 정답/오답", true)}
              <th className="num">오답 남음</th>
              {th("questions", "질문", true)}
              {th("visit", "마지막 접속일")}
            </tr>
          </thead>
          <tbody>
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
          <h2 className="heading">{issued.number} 등록 완료</h2>
          <p className="muted">아래 로그인 코드를 선수에게 전해 주세요. 서버에는 코드 원문이 남지 않아 지금만 볼 수 있어요.</p>
          <code className="issued-code">{issued.code}</code>
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
