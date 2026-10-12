import { ArrowRight, Plus, TriangleAlert, Wand2, X } from "lucide-react";
import { useState, type FormEvent } from "react";
import { api, type AthleteProfile, type CompetitionCategory, type ComputeRequest, type InputWarning } from "../api";
import { CATEGORY_LABEL } from "../session";
import { useSession } from "../session";
import { Select } from "./Select";

// DESIGN.md 7절 경기력 · D25: 선수가 최근 대회 기록을 직접 입력한다. 체급·합계는 서버가 도출.
// 입력값은 이 컴포넌트 상태에만 있고 서버에 저장되지 않는다.

interface Row {
  date: string;
  competition_category: CompetitionCategory;
  body_weight: string;
  snatch: string;
  clean_jerk: string;
}

const MIN_ROWS = 3;
const MAX_ROWS = 10;
// 연구진 RNN의 대회 분류 4종(schemas.CompetitionCategory). 범주를 잘못 고르면 예측이 수 kg 달라지므로 예시를 붙인다.
const CATEGORIES: { value: CompetitionCategory; label: string }[] = (Object.keys(CATEGORY_LABEL) as CompetitionCategory[]).map((value) => ({
  value,
  label: CATEGORY_LABEL[value],
}));
const CATEGORY_HELP = "세계대회: 올림픽·세계선수권·월드컵·유니버시아드 / 대륙대회: 아시안게임·아시아선수권 / 그 밖의 국제대회: 국제 초청대회·국제컵 / 국내 대회: 전국체전·국내 선수권 등";
const emptyRow = (): Row => ({ date: "", competition_category: "domestic", body_weight: "", snatch: "", clean_jerk: "" });

function toRequest(sex: "M" | "F", birthYear: string, rows: Row[], confirmed: boolean): ComputeRequest {
  return {
    sex,
    birth_year: Number(birthYear),
    confirmed,
    records: rows.map((r) => ({
      date: r.date,
      competition_category: r.competition_category,
      body_weight: Number(r.body_weight),
      snatch: Number(r.snatch),
      clean_jerk: Number(r.clean_jerk),
    })),
  };
}

const filled = (r: Row) => r.date && r.body_weight && r.snatch && r.clean_jerk;

export function RecordForm({ onResult }: { onResult: (p: AthleteProfile) => void }) {
  const { who, demo } = useSession();
  const [sex, setSex] = useState<"M" | "F">("M");
  const [birthYear, setBirthYear] = useState("");
  const [rows, setRows] = useState<Row[]>(() => Array.from({ length: 5 }, emptyRow));
  const [warnings, setWarnings] = useState<InputWarning[]>([]);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  const update = (i: number, patch: Partial<Row>) => {
    setWarnings([]);
    setRows((rs) => rs.map((r, k) => (k === i ? { ...r, ...patch } : r)));
  };

  const fillExample = async () => {
    if (!who.athlete_id) return;
    const ex = await api.demoExample(who.athlete_id);
    setSex(ex.sex);
    setBirthYear(String(ex.birth_year));
    setRows(
      ex.records.map((r) => ({
        date: r.date,
        competition_category: r.competition_category,
        body_weight: String(r.body_weight),
        snatch: String(r.snatch),
        clean_jerk: String(r.clean_jerk),
      })),
    );
    setWarnings([]);
    setError("");
  };

  const send = (confirmed: boolean) => {
    // 빈 행은 버리고 보낸다(기본 5행 중 일부만 채워도 됨)
    const used = rows.filter(filled);
    setError("");
    setPending(true);
    api
      .compute(toRequest(sex, birthYear, used, confirmed))
      .then(
        (res) => {
          setWarnings(res.warnings);
          if (res.profile) onResult(res.profile);
        },
        (e) => setError(e.message),
      )
      .finally(() => setPending(false));
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    send(false);
  };

  const usedCount = rows.filter(filled).length;
  const ready = birthYear.length === 4 && usedCount >= MIN_ROWS;

  return (
    <form className="card" onSubmit={submit} data-figure="input">
      <div className="row wrap" style={{ justifyContent: "space-between" }}>
        <h2 className="heading">최근 대회 기록 입력</h2>
        {demo && who.athlete_id && (
          <button type="button" className="btn-sub small" onClick={fillExample}>
            <Wand2 size={14} /> 예시 채우기 ({who.label})
          </button>
        )}
      </div>

      <div className="fields-2 narrow">
        <div className="field">
          <label className="label" htmlFor="sex">
            성별
          </label>
          <Select
            id="sex"
            value={sex}
            options={[
              { value: "M", label: "남자" },
              { value: "F", label: "여자" },
            ]}
            onChange={(v) => setSex(v)}
          />
        </div>
        <div className="field">
          <label className="label" htmlFor="birth-year">
            출생연도
          </label>
          <input
            id="birth-year"
            className="input num"
            inputMode="numeric"
            maxLength={4}
            value={birthYear}
            onChange={(e) => setBirthYear(e.target.value.replace(/\D/g, ""))}
            placeholder="예: 2007"
          />
        </div>
      </div>

      <div className="records" role="table" aria-label="대회 기록">
        <div className="records-head" role="row">
          <span role="columnheader">#</span>
          <span role="columnheader">대회 년-월</span>
          <span role="columnheader">대회 수준</span>
          <span role="columnheader">계체 체중(kg)</span>
          <span role="columnheader">인상(kg)</span>
          <span role="columnheader">용상(kg)</span>
          <span role="columnheader">합계</span>
          <span role="columnheader" aria-label="삭제" />
        </div>
        {rows.map((r, i) => {
          const total = Number(r.snatch) + Number(r.clean_jerk);
          const flagged = warnings.some((w) => w.row === i);
          return (
            <div key={i} className={`records-row${flagged ? " flagged" : ""}`} role="row">
              <span className="records-no caption">{i + 1}</span>
              <label className="records-cell">
                <span className="records-label">대회 년-월</span>
                <input className="input" type="month" value={r.date} onChange={(e) => update(i, { date: e.target.value })} aria-label={`${i + 1}번째 대회 년-월`} />
              </label>
              <label className="records-cell">
                <span className="records-label">대회 수준</span>
                <Select id={`category-${i}`} value={r.competition_category} options={CATEGORIES} onChange={(v) => update(i, { competition_category: v })} />
              </label>
              {(["body_weight", "snatch", "clean_jerk"] as const).map((f) => (
                <label key={f} className="records-cell">
                  <span className="records-label">{f === "body_weight" ? "계체 체중(kg)" : f === "snatch" ? "인상(kg)" : "용상(kg)"}</span>
                  <input
                    className="input num"
                    inputMode="decimal"
                    value={r[f]}
                    onChange={(e) => update(i, { [f]: e.target.value.replace(/[^\d.]/g, "") })}
                    aria-label={`${i + 1}번째 ${f === "body_weight" ? "계체 체중" : f === "snatch" ? "인상" : "용상"}`}
                  />
                </label>
              ))}
              <span className="records-total num">{r.snatch && r.clean_jerk ? `${total}` : "—"}</span>
              <button
                type="button"
                className="records-remove"
                onClick={() => setRows((rs) => rs.filter((_, k) => k !== i))}
                disabled={rows.length <= MIN_ROWS}
                aria-label={`${i + 1}번째 기록 삭제`}
              >
                <X size={16} />
              </button>
            </div>
          );
        })}
      </div>

      <div className="row wrap" style={{ justifyContent: "space-between" }}>
        <button type="button" className="btn-sub small" onClick={() => setRows((rs) => [...rs, emptyRow()])} disabled={rows.length >= MAX_ROWS}>
          <Plus size={14} /> 기록 추가
        </button>
        <p className="caption">오래된 대회부터 순서대로, 최소 {MIN_ROWS}개 · 입력한 기록은 저장되지 않아요</p>
      </div>
      <p className="caption">대회 수준 — {CATEGORY_HELP}</p>

      {warnings.length > 0 && (
        <div className="notice notice-caution" role="alert">
          <TriangleAlert size={18} />
          <div className="stack" style={{ gap: 6 }}>
            <strong>입력을 다시 확인해 주세요</strong>
            <ul className="steps">
              {warnings.map((w, k) => (
                <li key={k}>
                  {w.row !== null && `${w.row + 1}번째 기록: `}
                  {w.message}
                </li>
              ))}
            </ul>
            <button type="button" className="btn-sub small" style={{ alignSelf: "flex-start" }} onClick={() => send(true)} disabled={pending}>
              확인했어요, 이대로 계산하기
            </button>
          </div>
        </div>
      )}
      {error && <p className="error">{error}</p>}

      <button className="btn" style={{ alignSelf: "flex-start" }} disabled={!ready || pending}>
        교육 프로파일 만들기 <ArrowRight size={18} />
      </button>
    </form>
  );
}
