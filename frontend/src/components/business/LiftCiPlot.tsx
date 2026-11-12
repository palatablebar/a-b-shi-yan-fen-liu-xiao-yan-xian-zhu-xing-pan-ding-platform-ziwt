/** 效应量森林图：lift 点估计 + 95% CI，0 线判方向。自绘 SVG，不引入图表库。 */
import { fmtSignedPct } from '../../utils/format';

export interface LiftCiRow {
  label: string;
  lift: number | null;
  ci: [number, number] | null;
  significant?: boolean;
  muted?: boolean;
}

interface LiftCiPlotProps {
  rows: LiftCiRow[];
  title?: string;
}

const W = 560;
const ROW_H = 26;
const LEFT = 130;
const RIGHT = 86;

export const LiftCiPlot = ({ rows, title }: LiftCiPlotProps) => {
  const usable = rows.filter((row) => row.lift !== null);
  if (usable.length === 0) {
    return <p className="hint">暂无可绘制的效应量。</p>;
  }
  const bounds: number[] = [0];
  usable.forEach((row) => {
    bounds.push(row.lift ?? 0);
    if (row.ci) bounds.push(row.ci[0], row.ci[1]);
  });
  const min = Math.min(...bounds);
  const max = Math.max(...bounds);
  const pad = Math.max((max - min) * 0.12, 0.01);
  const lo = min - pad;
  const hi = max + pad;
  const scale = (value: number): number =>
    LEFT + ((value - lo) / (hi - lo)) * (W - LEFT - RIGHT);
  const height = 26 + usable.length * ROW_H;

  return (
    <svg
      className="plot"
      viewBox={`0 0 ${W} ${height}`}
      role="img"
      aria-label={title ?? '指标 lift 与 95% 置信区间'}
    >
      <line className="axis" x1={LEFT} y1={18} x2={LEFT} y2={height - 6} />
      <line className="zero" x1={scale(0)} y1={18} x2={scale(0)} y2={height - 6} />
      <text x={scale(0) + 4} y={14}>
        0
      </text>
      {usable.map((row, index) => {
        const y = 26 + index * ROW_H;
        const point = scale(row.lift ?? 0);
        const ciStart = row.ci ? scale(row.ci[0]) : point;
        const ciEnd = row.ci ? scale(row.ci[1]) : point;
        const tone = row.muted
          ? 'var(--ink-faint)'
          : row.significant
            ? 'var(--ok)'
            : 'var(--ink-soft)';
        return (
          <g key={row.label}>
            <text x={0} y={y + 4} style={{ fill: 'var(--ink-soft)' }}>
              {row.label}
            </text>
            <line x1={ciStart} y1={y} x2={ciEnd} y2={y} stroke={tone} strokeWidth={1.4} />
            <line x1={ciStart} y1={y - 5} x2={ciStart} y2={y + 5} stroke={tone} strokeWidth={1} />
            <line x1={ciEnd} y1={y - 5} x2={ciEnd} y2={y + 5} stroke={tone} strokeWidth={1} />
            <circle cx={point} cy={y} r={3.4} fill={tone} />
            <text x={W - RIGHT + 8} y={y + 4} style={{ fill: 'var(--ink)' }}>
              {fmtSignedPct(row.lift)}
            </text>
          </g>
        );
      })}
    </svg>
  );
};
