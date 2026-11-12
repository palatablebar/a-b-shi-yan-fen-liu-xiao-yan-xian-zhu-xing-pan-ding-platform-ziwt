/** 展示格式化（只格式化后端返回的数字，不参与统计计算）。 */

export const fmtPct = (value: number | null | undefined, digits = 2): string =>
  value === null || value === undefined ? '—' : `${(value * 100).toFixed(digits)}%`;

export const fmtSignedPct = (value: number | null | undefined, digits = 2): string => {
  if (value === null || value === undefined) return '—';
  const text = (value * 100).toFixed(digits);
  return `${value >= 0 ? '+' : ''}${text}%`;
};

export const fmtPp = (value: number | null | undefined, digits = 3): string => {
  if (value === null || value === undefined) return '—';
  const text = (value * 100).toFixed(digits);
  return `${value >= 0 ? '+' : ''}${text}pp`;
};

export const fmtNum = (value: number | null | undefined, digits = 2): string =>
  value === null || value === undefined ? '—' : value.toFixed(digits);

export const fmtInt = (value: number | null | undefined): string =>
  value === null || value === undefined ? '—' : value.toLocaleString('zh-CN');

export const fmtP = (value: number | null | undefined): string => {
  if (value === null || value === undefined) return '—';
  if (value < 0.0001) return '< 0.0001';
  return value.toFixed(4);
};

export const fmtQ = (value: number | null | undefined): string => {
  if (value === null || value === undefined) return '—';
  if (value < 0.0001) return '< 0.0001';
  return value.toFixed(3);
};

export const fmtDate = (value: string | null | undefined): string => {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' });
};

export const fmtDateTime = (value: string | null | undefined): string => {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

export const fmtRateOrMean = (
  value: number | null | undefined,
  kind: 'ratio' | 'mean',
  digits = 2,
): string => (kind === 'ratio' ? fmtPct(value, digits) : fmtNum(value, digits));

export const fmtLift = (value: number | null | undefined): string =>
  value === null || value === undefined ? '—' : fmtSignedPct(value, 2);

export const fmtCi = (ci: [number, number] | null | undefined): string =>
  ci ? `[${fmtSignedPct(ci[0])}, ${fmtSignedPct(ci[1])}]` : '—';
