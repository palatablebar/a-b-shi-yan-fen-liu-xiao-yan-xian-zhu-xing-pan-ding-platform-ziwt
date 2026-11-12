/** SRM 分流校验块：期望 vs 观测分桶条形图 + 卡方结论。详情页与批次结果页共用。 */
import type { SrmResult } from '../../types/models';
import { SRM_LABEL } from '../../constants/enums';
import { fmtInt, fmtP, fmtPct } from '../../utils/format';
import { srmTone } from '../../utils/display';
import { StatusPill } from '../common/StatusPill';
import { Annotation } from '../common/Annotation';

interface SrmBlockProps {
  srm: SrmResult | null | undefined;
  variantNames?: string[];
  compact?: boolean;
}

const BAR_W = 360;
const VIEW_W = BAR_W + 190;

export const SrmBlock = ({ srm, variantNames, compact = false }: SrmBlockProps) => {
  if (!srm) {
    return <p className="hint">暂无分流校验结果：先跑一次分析。</p>;
  }
  const observed = srm.observed_share ?? [];
  const expected = srm.expected_share ?? [];
  const names = variantNames ?? srm.variant_names ?? srm.variant_codes ?? ['对照', '实验'];
  const scale = Math.max(0.62, ...observed, ...expected) * 1.02;
  const height = 30 + observed.length * 58;

  return (
    <div>
      <div className="row-between" style={{ marginBottom: 8 }}>
        <StatusPill tone={srmTone(srm.verdict)}>{SRM_LABEL[srm.verdict]}</StatusPill>
        <span className="hint">
          曝光口径 · χ²={srm.chi2 ?? '—'} / df={srm.df ?? '—'} · p={fmtP(srm.p_value)}
        </span>
      </div>

      <svg
        className="plot"
        viewBox={`0 0 ${VIEW_W} ${height}`}
        role="img"
        aria-label="分流比例观测值与期望值对比"
      >
        {observed.map((share, index) => {
          const y = 16 + index * 58;
          const obsW = Math.max(2, (share / scale) * BAR_W);
          const expX = 110 + (expected[index] / scale) * BAR_W;
          return (
            <g key={names[index] ?? index}>
              <text x={0} y={y + 11} style={{ fill: 'var(--ink-soft)' }}>
                {names[index] ?? `变体 ${index + 1}`}
              </text>
              <rect x={110} y={y} width={BAR_W} height={14} fill="var(--paper-deep)" />
              <rect x={110} y={y} width={obsW} height={14} fill="var(--ink-soft)" />
              <line x1={expX} y1={y - 4} x2={expX} y2={y + 18} stroke="var(--red)" strokeWidth={1.5} />
              <text x={110 + BAR_W + 8} y={y + 11} style={{ fill: 'var(--ink)' }}>
                {fmtPct(share)}
              </text>
              <text x={110} y={y + 30} style={{ fill: 'var(--ink-faint)' }}>
                期望 {fmtPct(expected[index])} · 偏差 {((share - expected[index]) * 100).toFixed(3)}pp
              </text>
            </g>
          );
        })}
      </svg>

      <dl className="kv" style={{ marginTop: 10 }}>
        <dt>曝光总数</dt>
        <dd className="mono">{fmtInt(srm.total)}</dd>
        <dt>期望占比</dt>
        <dd className="mono">{expected.map((value) => fmtPct(value)).join(' / ')}</dd>
        <dt>观测占比</dt>
        <dd className="mono">{observed.map((value) => fmtPct(value)).join(' / ')}</dd>
        {!compact ? (
          <>
            <dt>判定阈值</dt>
            <dd className="mono">p &lt; {srm.threshold}</dd>
            <dt>结论</dt>
            <dd>{srm.reason}</dd>
          </>
        ) : null}
      </dl>

      {srm.verdict === 'detected' ? (
        <Annotation>
          分流失衡期间指标差异不可采信：本批次已锁定为「不可读」，必须先修分流器/埋点再重跑。
        </Annotation>
      ) : null}
    </div>
  );
};
