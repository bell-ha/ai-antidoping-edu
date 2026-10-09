import type { ForecastPoint, RecordPoint } from "../api";

// DESIGN.md 7절 · D19: 직접 SVG. 실제 = 검정 실선·점, 예측 평균 = 회색 점선, 예측 구간 = --app-line 띠 + 점선 경계.
// 흑백 인쇄에서도 선 모양으로 구분된다. 툴팁·애니메이션 없음.

const W = 340;
const H = 226;
const PAD = { top: 28, right: 12, bottom: 26, left: 36 };

const months = (d: string) => {
  const [y, m] = d.split("-").map(Number);
  return y * 12 + (m - 1);
};

function ticks(lo: number, hi: number, count = 4): number[] {
  const step = Math.max(5, Math.ceil((hi - lo) / count / 5) * 5);
  const start = Math.ceil(lo / step) * step;
  const out: number[] = [];
  for (let v = start; v <= hi; v += step) out.push(v);
  return out;
}

export function RecordChart({ records, forecast }: { records: RecordPoint[]; forecast: ForecastPoint[] }) {
  const xs = [...records.map((r) => months(r.date)), ...forecast.map((f) => months(f.date))];
  const ys = [...records.map((r) => r.total), ...forecast.flatMap((f) => [f.lo, f.hi])];
  const [x0, x1] = [Math.min(...xs), Math.max(...xs)];
  const [yMin, yMax] = [Math.min(...ys), Math.max(...ys)];
  const yPad = (yMax - yMin) * 0.08 || 5;
  const [y0, y1] = [yMin - yPad, yMax + yPad];

  const x = (d: string) => PAD.left + ((months(d) - x0) / (x1 - x0 || 1)) * (W - PAD.left - PAD.right);
  const y = (v: number) => PAD.top + (1 - (v - y0) / (y1 - y0)) * (H - PAD.top - PAD.bottom);
  const path = (pts: [number, number][]) => pts.map(([px, py], i) => `${i ? "L" : "M"}${px.toFixed(1)},${py.toFixed(1)}`).join("");

  const band =
    path(forecast.map((f) => [x(f.date), y(f.hi)])) +
    [...forecast].reverse().map((f) => `L${x(f.date).toFixed(1)},${y(f.lo).toFixed(1)}`).join("") +
    "Z";

  const classChanges = records.flatMap((r, i) =>
    i > 0 && r.weight_class !== records[i - 1].weight_class ? [{ date: r.date, from: records[i - 1].weight_class, to: r.weight_class }] : [],
  );
  const years = [...new Set(records.map((r) => r.date.slice(0, 4)))].filter((_, i, a) => a.length <= 5 || i % 2 === 0);

  return (
    <div className="stack">
      <div className="legend">
        <span>
          <svg width="20" height="8" aria-hidden>
            <line x1="0" y1="4" x2="20" y2="4" stroke="var(--text)" strokeWidth="2" />
          </svg>
          실제 기록(합계)
        </span>
        <span>
          <svg width="20" height="8" aria-hidden>
            <line x1="0" y1="4" x2="20" y2="4" stroke="var(--text-sub)" strokeWidth="1.5" strokeDasharray="4 3" />
          </svg>
          예측
        </span>
        <span>
          <svg width="14" height="10" aria-hidden>
            <rect width="14" height="10" fill="var(--app-line)" />
          </svg>
          예측 범위
        </span>
      </div>
      <svg className="chart num" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="경기 기록과 예측 범위">
        {ticks(y0, y1).map((v) => (
          <g key={v}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(v)} y2={y(v)} stroke="var(--line)" />
            <text x={PAD.left - 6} y={y(v) + 4} textAnchor="end" fontSize="11" fill="var(--text-faint)">
              {v}
            </text>
          </g>
        ))}
        {years.map((yr) => (
          <text key={yr} x={x(`${yr}-01`)} y={H - 8} textAnchor="middle" fontSize="11" fill="var(--text-faint)">
            {yr}
          </text>
        ))}

        <path d={band} fill="var(--app-line)" opacity="0.7" />
        <path d={path(forecast.map((f) => [x(f.date), y(f.hi)]))} fill="none" stroke="var(--app-ink)" strokeWidth="0.75" strokeDasharray="2 2" />
        <path d={path(forecast.map((f) => [x(f.date), y(f.lo)]))} fill="none" stroke="var(--app-ink)" strokeWidth="0.75" strokeDasharray="2 2" />
        <path d={path(forecast.map((f) => [x(f.date), y(f.mean)]))} fill="none" stroke="var(--text-sub)" strokeWidth="1.5" strokeDasharray="4 3" />

        {classChanges.map((c) => (
          <g key={c.date}>
            <line x1={x(c.date)} x2={x(c.date)} y1={PAD.top} y2={H - PAD.bottom} stroke="var(--text-sub)" strokeDasharray="3 3" />
            {/* 라벨은 그림 영역 위 여백에 둬서 예측 띠와 겹치지 않게 */}
            <text x={Math.min(x(c.date), W - PAD.right)} y={PAD.top - 10} textAnchor="end" fontSize="11" fill="var(--text-sub)">
              체급 {c.from}→{c.to}
            </text>
          </g>
        ))}

        <path d={path(records.map((r) => [x(r.date), y(r.total)]))} fill="none" stroke="var(--text)" strokeWidth="2" />
        {records.map((r) => (
          <circle key={r.date} cx={x(r.date)} cy={y(r.total)} r="2.5" fill="var(--text)" />
        ))}
      </svg>
      <p className="caption">단위 kg · 2018 IWF 체급 기준</p>
    </div>
  );
}
