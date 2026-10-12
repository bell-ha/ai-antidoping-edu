import { useEffect, useRef, useState } from "react";
import type { ForecastPoint, RecordPoint } from "../api";

// DESIGN.md 7절 · D19: 직접 SVG. 실제 = 검정 실선·점, 예측 평균 = 회색 점선, 예측 구간 = --app-line 띠 + 점선 경계.
// 흑백 인쇄에서도 선 모양으로 구분된다. 툴팁·애니메이션 없음.
// 비율은 16:9로 고정하고, 컨테이너 폭을 재서 그 폭 그대로 그린다(viewBox를 늘이고 줄이면 폰에서 축 글자가 작아짐).

const PAD = { top: 30, right: 16, bottom: 30, left: 44 };
const FONT = 12;

const months = (d: string) => {
  const [y, m] = d.split("-").map(Number);
  return y * 12 + (m - 1);
};

// 눈금 간격을 5의 배수로 잡고, 축 범위를 그 간격에 맞춰 넓혀 데이터(예측 띠 포함)가 항상 눈금 안에 들어오게 한다
function niceAxis(lo: number, hi: number, count = 5): { y0: number; y1: number; ticks: number[] } {
  const step = Math.max(5, Math.ceil((hi - lo) / count / 5) * 5);
  const y0 = Math.floor(lo / step) * step;
  const y1 = Math.ceil(hi / step) * step;
  const ticks: number[] = [];
  for (let v = y0; v <= y1; v += step) ticks.push(v);
  return { y0, y1, ticks };
}

export function useWidth() {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.round(e.contentRect.width)));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, width] as const;
}

export function RecordChart({ records, forecast, caption }: { records: RecordPoint[]; forecast: ForecastPoint[]; caption: string }) {
  const hasForecast = forecast.length > 0; // 해당 성별 모델이 없으면 예측을 그리지 않는다
  const [ref, W] = useWidth();
  const H = Math.round((W * 9) / 16);

  return (
    <div className="stack">
      <div className="legend">
        <span>
          <svg width="20" height="8" aria-hidden>
            <line x1="0" y1="4" x2="20" y2="4" stroke="var(--ink)" strokeWidth="2" />
          </svg>
          실제 기록(합계)
        </span>
        {hasForecast && (
          <>
            <span>
              <svg width="20" height="8" aria-hidden>
                <line x1="0" y1="4" x2="20" y2="4" stroke="var(--muted)" strokeWidth="1.5" strokeDasharray="4 3" />
              </svg>
              예측
            </span>
            <span>
              <svg width="14" height="10" aria-hidden>
                <rect width="14" height="10" fill="var(--app-line)" />
              </svg>
              예측 범위
            </span>
          </>
        )}
      </div>
      <div ref={ref}>{W > 0 && <Plot records={records} forecast={forecast} W={W} H={H} />}</div>
      <p className="caption">{caption}</p>
    </div>
  );
}

function Plot({ records, forecast, W, H }: { records: RecordPoint[]; forecast: ForecastPoint[]; W: number; H: number }) {
  const xs = [...records.map((r) => months(r.date)), ...forecast.map((f) => months(f.date))];
  const ys = [...records.map((r) => r.total), ...forecast.flatMap((f) => [f.lo, f.hi])];
  const [x0, x1] = [Math.min(...xs), Math.max(...xs)];
  const { y0, y1, ticks } = niceAxis(Math.min(...ys), Math.max(...ys));

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
  const allYears = [...new Set(records.map((r) => r.date.slice(0, 4)))];
  const every = Math.ceil(allYears.length / Math.max(2, Math.floor(W / 90)));
  const years = allYears.filter((_, i) => i % every === 0);

  return (
    <svg className="chart num" width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label="경기 기록과 예측 범위">
      {ticks.map((v) => (
        <g key={v}>
          <line x1={PAD.left} x2={W - PAD.right} y1={y(v)} y2={y(v)} stroke="var(--hairline)" />
          <text x={PAD.left - 8} y={y(v) + 4} textAnchor="end" fontSize={FONT} fill="var(--muted)">
            {v}
          </text>
        </g>
      ))}
      {years.map((yr) => (
        <text key={yr} x={Math.max(PAD.left, x(`${yr}-01`))} y={H - 8} textAnchor="middle" fontSize={FONT} fill="var(--muted)">
          {yr}
        </text>
      ))}

      {forecast.length > 0 && <path d={band} fill="var(--app-line)" opacity="0.7" />}
      <path d={path(forecast.map((f) => [x(f.date), y(f.hi)]))} fill="none" stroke="var(--app-ink)" strokeWidth="0.75" strokeDasharray="2 2" />
      <path d={path(forecast.map((f) => [x(f.date), y(f.lo)]))} fill="none" stroke="var(--app-ink)" strokeWidth="0.75" strokeDasharray="2 2" />
      <path d={path(forecast.map((f) => [x(f.date), y(f.mean)]))} fill="none" stroke="var(--muted)" strokeWidth="1.5" strokeDasharray="4 3" />

      {classChanges.map((c) => (
        <g key={c.date}>
          <line x1={x(c.date)} x2={x(c.date)} y1={PAD.top} y2={H - PAD.bottom} stroke="var(--muted)" strokeDasharray="3 3" />
          {/* 라벨은 그림 영역 위 여백에 둬서 예측 띠와 겹치지 않게 */}
          <text x={Math.min(x(c.date), W - PAD.right)} y={PAD.top - 10} textAnchor="end" fontSize={FONT} fill="var(--ink)">
            체급 {c.from}→{c.to}
          </text>
        </g>
      ))}

      <path d={path(records.map((r) => [x(r.date), y(r.total)]))} fill="none" stroke="var(--ink)" strokeWidth="2" />
      {records.map((r) => (
        <circle key={r.date} cx={x(r.date)} cy={y(r.total)} r="3" fill="var(--ink)" />
      ))}
    </svg>
  );
}
