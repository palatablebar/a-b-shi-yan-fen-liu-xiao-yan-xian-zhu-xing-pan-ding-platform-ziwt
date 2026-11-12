/** 变体与分桶：用户数 / 曝光数 / 观测占比 vs 期望占比。 */
import type { Variant } from '../../types/models';
import { fmtInt, fmtPct } from '../../utils/format';
import { StatusPill } from '../common/StatusPill';

interface VariantSplitProps {
  variants: Variant[];
  expected: number[];
}

export const VariantSplit = ({ variants, expected }: VariantSplitProps) => {
  const totalExposures = variants.reduce((sum, variant) => sum + variant.exposures, 0) || 1;
  return (
    <div className="variant-grid">
      {variants.map((variant, index) => {
        const share = variant.exposures / totalExposures;
        const expectedShare = expected[index] ?? variant.traffic_allocation;
        const deviation = (share - expectedShare) * 100;
        return (
          <div key={variant.id} className={`variant-card${variant.is_control ? ' control' : ''}`}>
            <div className="row-between">
              <span className="variant-code">{variant.code}</span>
              <StatusPill tone={Math.abs(deviation) > 1 ? 'fail' : 'ok'}>
                {Math.abs(deviation) > 1 ? '偏差偏大' : '配比正常'}
              </StatusPill>
            </div>
            <h4>{variant.name}</h4>
            <p className="hint">{variant.description}</p>
            <dl className="kv" style={{ marginTop: 8 }}>
              <dt>分桶用户</dt>
              <dd className="mono">{fmtInt(variant.users)}</dd>
              <dt>曝光次数</dt>
              <dd className="mono">{fmtInt(variant.exposures)}</dd>
              <dt>观测占比</dt>
              <dd className="mono">
                {fmtPct(share)}
                <span className="hint" style={{ marginLeft: 6 }}>
                  期望 {fmtPct(expectedShare)}
                </span>
              </dd>
            </dl>
          </div>
        );
      })}
    </div>
  );
};
