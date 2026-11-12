/** 守卫指标检查：显著变差 → 结论降级。 */
import type { GuardResult } from '../../types/models';
import { GUARD_STATE_LABEL } from '../../constants/enums';
import { fmtP, fmtQ, fmtSignedPct } from '../../utils/format';
import { guardTone } from '../../utils/display';
import { StatusPill } from '../common/StatusPill';

interface GuardGridProps {
  guard: GuardResult | null | undefined;
}

export const GuardGrid = ({ guard }: GuardGridProps) => {
  if (!guard || guard.checks.length === 0) {
    return <p className="hint">本实验未配置守卫指标。建议至少配置一个「越低越好」的体验类指标。</p>;
  }
  return (
    <div className="guard-grid">
      {guard.checks.map((check) => (
        <div key={check.code} className={`guard-card ${check.state}`}>
          <div className="row-between">
            <strong>{check.name}</strong>
            <StatusPill tone={guardTone(check.state)}>{GUARD_STATE_LABEL[check.state]}</StatusPill>
          </div>
          <dl className="kv" style={{ marginTop: 8 }}>
            <dt>lift</dt>
            <dd className="mono">{fmtSignedPct(check.lift)}</dd>
            <dt>p / q</dt>
            <dd className="mono">
              {fmtP(check.p_value)} / {fmtQ(check.q_value)}
            </dd>
            <dt>方向</dt>
            <dd className="hint">
              {check.bad_direction ? '变差方向' : '变好方向'} · {check.note}
            </dd>
          </dl>
        </div>
      ))}
      {guard.regression ? (
        <p className="hint" style={{ gridColumn: '1 / -1', color: 'var(--fail)' }}>
          守卫指标显著变差 → 按固定规则结论降级为 fail。
        </p>
      ) : null}
    </div>
  );
};
