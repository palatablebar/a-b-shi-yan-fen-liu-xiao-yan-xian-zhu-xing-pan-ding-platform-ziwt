/** 数字展示：等宽、千分位、带涨跌方向。所有统计数字来自后端。 */
import { fmtInt, fmtLift, fmtNum, fmtP, fmtPct } from '../../utils/format';

interface MetricNumProps {
  value: number | null | undefined;
  kind?: 'pct' | 'num' | 'int' | 'p' | 'lift';
  digits?: number;
  unit?: string;
  signed?: boolean;
  className?: string;
}

export const MetricNum = ({
  value,
  kind = 'num',
  digits = 2,
  unit,
  signed = false,
  className = '',
}: MetricNumProps) => {
  let text: string;
  if (kind === 'pct') text = fmtPct(value, digits);
  else if (kind === 'int') text = fmtInt(value);
  else if (kind === 'p') text = fmtP(value);
  else if (kind === 'lift') text = fmtLift(value);
  else text = fmtNum(value, digits);

  const numeric = value ?? 0;
  const tone = signed ? (numeric > 0 ? 'pos' : numeric < 0 ? 'neg' : '') : '';
  return (
    <span className={`metric-num ${tone} ${className}`.trim()}>
      {text}
      {unit ? <span className="unit">{unit}</span> : null}
    </span>
  );
};
