import type { ResidualPoint } from "../api";
import { useWidth } from "./RecordChart";

// D32: 대회별 관측 − 예측(kg) 막대. σ가 아니라 kg로 보여준다(대회별 z 값 시계열은 점수판처럼 읽힘, D7).
// 위(+)는 예측보다 높았던 대회, 아래(−)는 낮았던 대회. 색으로 좋고 나쁨을 나타내지 않는다.

const H = 160;
const PAD = { top: 12, right: 12, bottom: 28, left: 44 };

export function ResidualChart({ points }: { points: ResidualPoint[] }) {
  const [ref, width] = useWidth();
  return <div ref={ref}>{width > 0 && points.length > 0 && <Bars points={points} width={width} />}</div>;
}

function Bars({ points, width }: { points: ResidualPoint[]; width: number }) {
  const max = Math.max(5, ...points.map((p) => Math.abs(p.diff_kg)));
  const lim = Math.ceil(max / 5) * 5;
  const innerW = width - PAD.left - PAD.right;
  const bw = Math.min(28, (innerW / points.length) * 0.6);
  const cx = (i: number) => PAD.left + ((i + 0.5) / points.length) * innerW;
  const y = (v: number) => PAD.top + ((lim - v) / (2 * lim)) * (H - PAD.top - PAD.bottom);
  const every = Math.ceil(points.length / Math.max(2, Math.floor(innerW / 70)));

  return (
    <svg className="chart num" width={width} height={H} viewBox={`0 0 ${width} ${H}`} role="img" aria-label="대회별 예측과의 차이(kg)">
      {[lim, 0, -lim].map((v) => (
        <g key={v}>
          <line x1={PAD.left} x2={width - PAD.right} y1={y(v)} y2={y(v)} stroke={v === 0 ? "var(--muted)" : "var(--hairline)"} />
          <text x={PAD.left - 8} y={y(v) + 4} textAnchor="end" fontSize={12} fill="var(--muted)">
            {v > 0 ? `+${v}` : v}
          </text>
        </g>
      ))}
      {points.map((p, i) => (
        <g key={p.date}>
          <rect
            x={cx(i) - bw / 2}
            y={Math.min(y(p.diff_kg), y(0))}
            width={bw}
            height={Math.max(1, Math.abs(y(p.diff_kg) - y(0)))}
            fill="var(--app-line)"
            stroke="var(--app-ink)"
            strokeWidth="0.75"
          >
            <title>{`${p.date} · 실제 ${p.observed}kg · 예측 ${p.predicted.toFixed(1)}kg · 차이 ${p.diff_kg > 0 ? "+" : ""}${p.diff_kg.toFixed(1)}kg`}</title>
          </rect>
          {i % every === 0 && (
            <text x={cx(i)} y={H - 8} textAnchor="middle" fontSize={12} fill="var(--muted)">
              {p.date.slice(2).replace("-", ".")}
            </text>
          )}
        </g>
      ))}
    </svg>
  );
}
