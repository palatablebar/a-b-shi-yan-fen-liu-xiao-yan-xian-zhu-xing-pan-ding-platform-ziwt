/**
 * 多臂实验看板：共同对照 + 多处理方案。
 * 看清三件事：
 * 1) 每个方案与同一对照臂的关系（配对 SRM、曝光/用户对账、流量配比）；
 * 2) 主指标/守卫指标的原始 p 与全方案统一 BH 校正后 q（校正前后并列）；
 * 3) 每个方案的四档 verdict 与可上线状态 ship_state——
 *    守卫生效或校正后失真的方案一律 blocked，不能被当成赢家。
 */
import { useMemo, useState } from 'react';
import type { ArmResult, ComparisonRow, RunDetail, ShipState } from '../../types/models';
import { SHIP_STATE_HINT, SHIP_STATE_LABEL, SRM_LABEL } from '../../constants/enums';
import { shipStateTone, srmTone, verdictTone } from '../../utils/display';
import { fmtInt, fmtP, fmtPct, fmtQ, fmtSignedPct } from '../../utils/format';
import { RuledTable, type Column } from '../common/RuledTable';
import { SheetPanel } from '../common/SheetPanel';
import { StatusPill } from '../common/StatusPill';
import { VerdictStamp } from '../common/VerdictStamp';
import { Annotation } from '../common/Annotation';
import { GuardGrid } from './GuardGrid';

interface MultiArmBoardProps {
  run: RunDetail;
  alpha: number;
}

const FAMILY_LABEL: Record<string, string> = {
  primary: '主指标',
  guard: '守卫指标',
  secondary: '辅助指标',
  strata: '分层',
};

export const MultiArmBoard = ({ run, alpha }: MultiArmBoardProps) => {
  const arms = run.arms ?? [];
  const [activeCode, setActiveCode] = useState<string>(arms[0]?.variant.code ?? '');
  const active = useMemo(
    () => arms.find((arm) => arm.variant.code === activeCode) ?? arms[0],
    [arms, activeCode],
  );

  const controlName = arms[0]?.control_variant.name ?? '共同对照';
  const winnerCount = arms.filter((arm) => arm.ship_state === 'ship_eligible').length;

  return (
    <div className="stack">
      {/* ---------------- 总览：方案对照关系 + 校正前后 + 可上线状态 ---------------- */}
      <SheetPanel
        title="多方案对照总览（共同对照）"
        index="M1"
        note={`${arms.length} 个处理方案 · 全部对照「${controlName}」`}
        actions={
          <StatusPill tone={winnerCount === 1 ? 'ok' : winnerCount > 1 ? 'warn' : 'fail'}>
            可上线 {winnerCount} 个
          </StatusPill>
        }
      >
        <RuledTable
          columns={armOverviewColumns(alpha)}
          rows={arms}
          rowKey={(arm) => arm.variant.code}
          flagged={(arm) => arm.ship_state === 'blocked'}
        />
        <Annotation>
          每行是一个处理方案与同一对照臂的配对结果。原始 p 是该方案自身的检验，
          全方案 BH q 是把所有方案的主/守卫/辅助/分层检验合并进同一个 family 后的校正结果；
          校正后 q ≥ α（校正失真）或守卫显著变差的方案为 blocked，不能被当成赢家。
        </Annotation>
      </SheetPanel>

      {/* ---------------- 分桶曝光与流量配比对账 ---------------- */}
      <SheetPanel title="分桶曝光与流量配比对账" index="M2" note="曝光口径 SRM · 全实验 + 逐方案配对两档">
        <div className="row-between" style={{ marginBottom: 8, flexWrap: 'wrap', gap: 8 }}>
          <StatusPill tone={srmTone(run.srm?.verdict)}>
            全实验 {SRM_LABEL[run.srm?.verdict ?? 'ok']}
          </StatusPill>
          <span className="hint mono">
            χ²={run.srm?.chi2 ?? '—'} / df={run.srm?.df ?? '—'} · p={fmtP(run.srm?.p_value ?? null)} ·
            曝光总数 {fmtInt(run.srm?.total ?? null)}
          </span>
        </div>
        <RuledTable
          columns={reconcileColumns()}
          rows={arms}
          rowKey={(arm) => `srm-${arm.variant.code}`}
          flagged={(arm) => arm.srm_pair.verdict === 'detected'}
        />
      </SheetPanel>

      {active ? (
        <>
          {/* ---------------- 方案切换 + 判定理由 ---------------- */}
          <SheetPanel
            title={`方案明细 · ${active.variant.name}`}
            index="M3"
            note={`对照臂：${active.control_variant.name}（${active.control_variant.code}）`}
            actions={
              <div className="row" style={{ gap: 8 }}>
                <VerdictStamp verdict={active.verdict} large animate={false} />
                <StatusPill tone={shipStateTone(active.ship_state)}>
                  {SHIP_STATE_LABEL[active.ship_state]}
                </StatusPill>
              </div>
            }
          >
            <div className="filter-tabs" role="tablist" style={{ marginBottom: 12 }}>
              {arms.map((arm) => (
                <button
                  key={arm.variant.code}
                  role="tab"
                  aria-selected={arm.variant.code === active.variant.code}
                  className={`filter-tab${arm.variant.code === active.variant.code ? ' active' : ''}`}
                  onClick={() => setActiveCode(arm.variant.code)}
                >
                  {arm.variant.name}
                  <span className="count">{SHIP_STATE_LABEL[arm.ship_state]}</span>
                </button>
              ))}
            </div>

            <ArmPrimaryCard arm={active} alpha={alpha} />

            <ul className="reason-list" style={{ marginTop: 10 }}>
              {active.verdict_reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
            <p className="hint" style={{ marginTop: 8 }}>
              可上线状态说明：{SHIP_STATE_HINT[active.ship_state]}
            </p>
          </SheetPanel>

          {/* ---------------- 守卫指标 ---------------- */}
          <SheetPanel
            title={`守卫指标 · ${active.variant.name}`}
            index="M4"
            note="显著变差（守卫族内 BH）→ 该方案 blocked"
          >
            <GuardGrid guard={active.guard} />
          </SheetPanel>

          {/* ---------------- 分层：分层内 BH + 全方案 BH ---------------- */}
          <SheetPanel
            title={`分层下钻 · ${active.variant.name}`}
            index="M5"
            note={`城市 × 客群 · 分层内 BH m=${active.strata.family.m} · 另给全方案 BH q`}
          >
            <RuledTable
              columns={strataColumns(alpha, active.primary.kind)}
              rows={active.strata.cells}
              rowKey={(cell) => `${cell.segment_city}-${cell.segment_tenure}`}
              flagged={(cell) => Boolean(cell.significant_raw && !cell.significant_bh)}
            />
          </SheetPanel>
        </>
      ) : null}

      {/* ---------------- 全方案统一 BH 明细 ---------------- */}
      <SheetPanel
        title="全方案统一 BH（所有检验合并一个族）"
        index="M6"
        note={`m=${run.comparisons?.length ?? 0} · 同一套误报控制覆盖全部方案`}
        dense
      >
        <RuledTable
          columns={fullFamilyColumns(alpha)}
          rows={(run.comparisons ?? []) as ComparisonRow[]}
          rowKey={(row, index) => `${row.arm_code ?? 'arm'}-${row.family}-${row.label}-${index}`}
          flagged={(row) => Boolean(row.p_value < alpha && !row.reject)}
        />
      </SheetPanel>
    </div>
  );
};

/* ------------------------------------------------------------------ 列定义 ---- */

function armOverviewColumns(alpha: number): Column<ArmResult>[] {
  return [
    {
      key: 'variant',
      label: '处理方案（vs 共同对照）',
      render: (arm) => (
        <div>
          <strong>{arm.variant.name}</strong>
          <div className="hint mono" style={{ marginTop: 2 }}>
            {arm.variant.code} ← {arm.control_variant.code}
          </div>
        </div>
      ),
    },
    {
      key: 'n',
      label: '用户（对照/方案）',
      align: 'right',
      render: (arm) => (
        <span className="mono">
          {fmtInt(arm.sample.control_users)} / {fmtInt(arm.sample.treat_users)}
        </span>
      ),
    },
    {
      key: 'lift',
      label: '主指标 lift',
      align: 'right',
      render: (arm) => (
        <span className={arm.primary.lift !== null && arm.primary.lift < 0 ? 'neg-text' : ''}>
          {fmtSignedPct(arm.primary.lift)}
        </span>
      ),
    },
    {
      key: 'ci',
      label: 'lift 95% CI',
      align: 'right',
      render: (arm) => (
        <span className="hint">
          {arm.primary.lift_ci95
            ? `[${fmtSignedPct(arm.primary.lift_ci95[0])}, ${fmtSignedPct(arm.primary.lift_ci95[1])}]`
            : '—'}
        </span>
      ),
    },
    {
      key: 'p',
      label: '原始 p',
      align: 'right',
      render: (arm) => (
        <span className={arm.primary.p_value !== null && arm.primary.p_value < alpha ? 'sig-text' : ''}>
          {fmtP(arm.primary.p_value)}
        </span>
      ),
    },
    {
      key: 'q',
      label: '全方案 BH q',
      align: 'right',
      render: (arm) => (
        <span className={arm.primary.bh_reject ? 'sig-text' : arm.bh_distorted ? 'neg-text' : ''}>
          {fmtQ(arm.primary.q_value)}
        </span>
      ),
    },
    {
      key: 'guard',
      label: '守卫',
      align: 'center',
      render: (arm) =>
        arm.guard_regression ? (
          <StatusPill tone="fail">守卫回归</StatusPill>
        ) : (
          <StatusPill tone="ok">无回归</StatusPill>
        ),
    },
    {
      key: 'verdict',
      label: '结论',
      align: 'center',
      render: (arm) => <VerdictStamp verdict={arm.verdict} animate={false} />,
    },
    {
      key: 'ship',
      label: '可上线状态',
      align: 'center',
      render: (arm) => (
        <StatusPill tone={shipStateTone(arm.ship_state)}>
          {SHIP_STATE_LABEL[arm.ship_state as ShipState]}
        </StatusPill>
      ),
    },
  ];
}

function reconcileColumns(): Column<ArmResult>[] {
  return [
    {
      key: 'pair',
      label: '配对（共同对照 vs 方案）',
      render: (arm) => (
        <span>
          <strong>{arm.control_variant.name}</strong>
          <span className="hint"> vs </span>
          <strong>{arm.variant.name}</strong>
        </span>
      ),
    },
    {
      key: 'exposures',
      label: '曝光（对照/方案）',
      align: 'right',
      render: (arm) => (
        <span className="mono">
          {fmtInt(arm.sample.control_exposures)} / {fmtInt(arm.sample.treat_exposures)}
        </span>
      ),
    },
    {
      key: 'observed',
      label: '观测占比（对照/方案）',
      align: 'right',
      render: (arm) => (
        <span className="mono">
          {fmtPct(arm.srm_pair.observed_share?.[0])} / {fmtPct(arm.srm_pair.observed_share?.[1])}
        </span>
      ),
    },
    {
      key: 'expected',
      label: '期望配比（对照/方案）',
      align: 'right',
      render: (arm) => (
        <span className="mono">
          {fmtPct(arm.srm_pair.expected_share?.[0])} / {fmtPct(arm.srm_pair.expected_share?.[1])}
        </span>
      ),
    },
    {
      key: 'chi2',
      label: 'χ²',
      align: 'right',
      render: (arm) => <span className="mono">{arm.srm_pair.chi2 ?? '—'}</span>,
    },
    {
      key: 'p',
      label: '配对 SRM p',
      align: 'right',
      render: (arm) => <span className="mono">{fmtP(arm.srm_pair.p_value)}</span>,
    },
    {
      key: 'verdict',
      label: '判定',
      align: 'center',
      render: (arm) => (
        <StatusPill tone={srmTone(arm.srm_pair.verdict)}>
          {SRM_LABEL[arm.srm_pair.verdict ?? 'ok']}
        </StatusPill>
      ),
    },
  ];
}

function strataColumns(alpha: number, kind: 'ratio' | 'mean'): Column<ArmResult['strata']['cells'][number]>[] {
  return [
    {
      key: 'cell',
      label: '分层（城市 × 客群）',
      render: (cell) => (
        <span>
          {cell.segment_city} · {cell.segment_tenure}
        </span>
      ),
    },
    {
      key: 'n',
      label: '对照 n / 方案 n',
      align: 'right',
      render: (cell) => (
        <span className="mono">
          {cell.control_n} / {cell.treat_n}
        </span>
      ),
    },
    {
      key: 'control',
      label: '对照组',
      align: 'right',
      render: (cell) =>
        cell.control_value === null
          ? '—'
          : kind === 'ratio'
            ? fmtPct(cell.control_value)
            : cell.control_value.toFixed(2),
    },
    {
      key: 'treat',
      label: '方案组',
      align: 'right',
      render: (cell) =>
        cell.treat_value === null
          ? '—'
          : kind === 'ratio'
            ? fmtPct(cell.treat_value)
            : cell.treat_value.toFixed(2),
    },
    {
      key: 'lift',
      label: 'lift',
      align: 'right',
      render: (cell) => fmtSignedPct(cell.lift),
    },
    {
      key: 'p',
      label: '原始 p',
      align: 'right',
      render: (cell) => <span className={cell.significant_raw ? 'sig-text' : ''}>{fmtP(cell.p_value)}</span>,
    },
    {
      key: 'q_inner',
      label: '分层内 BH q',
      align: 'right',
      render: (cell) => <span className={cell.significant_bh ? 'sig-text' : ''}>{fmtQ(cell.q_value)}</span>,
    },
    {
      key: 'q_full',
      label: '全方案 BH q',
      align: 'right',
      render: (cell) => (
        <span className={cell.full_bh_reject ? 'sig-text' : ''}>{fmtQ(cell.full_bh_q_value ?? null)}</span>
      ),
    },
    {
      key: 'verdict',
      label: '判定',
      align: 'center',
      render: (cell) => {
        if (cell.p_value === null) return <span className="pill">不可检验</span>;
        if (cell.significant_bh) return <span className="pill ok">分层 BH 后显著</span>;
        if (cell.significant_raw) return <span className="pill warn">校正后不显著</span>;
        return <span className="pill">不显著</span>;
      },
    },
  ];
}

function fullFamilyColumns(alpha: number): Column<ComparisonRow>[] {
  return [
    { key: 'arm', label: '方案', render: (row) => <strong>{row.arm_name ?? '—'}</strong> },
    { key: 'label', label: '检验项', render: (row) => row.label },
    {
      key: 'family',
      label: '族',
      render: (row) => <span className="hint">{FAMILY_LABEL[row.family] ?? row.family}</span>,
    },
    {
      key: 'p',
      label: '原始 p',
      align: 'right',
      render: (row) => <span className={row.p_value < alpha ? 'sig-text' : ''}>{fmtP(row.p_value)}</span>,
    },
    {
      key: 'q',
      label: '全方案 q',
      align: 'right',
      render: (row) => <span className={row.reject ? 'sig-text' : ''}>{fmtQ(row.q_value)}</span>,
    },
    {
      key: 'rank',
      label: '秩',
      align: 'right',
      render: (row) => <span className="mono">{row.rank ?? '—'}</span>,
    },
    {
      key: 'reject',
      label: 'BH 后',
      align: 'center',
      render: (row) =>
        row.reject ? <span className="pill ok">显著</span> : <span className="pill">不显著</span>,
    },
  ];
}

/* ------------------------------------------------------------- 方案主指标卡 ---- */

const ArmPrimaryCard = ({ arm, alpha }: { arm: ArmResult; alpha: number }) => {
  const p = arm.primary;
  const kind = p.kind;
  const fmtValue = (value: number | null) =>
    value === null ? '—' : kind === 'ratio' ? fmtPct(value) : value.toFixed(2);
  return (
    <div className="split split-3">
      <div className="stat-block">
        <span className="stat-label">主指标（对照 → 方案）</span>
        <div className="big-num" style={{ fontSize: 18 }}>
          {fmtValue(p.control_value)} → {fmtValue(p.treat_value)}
        </div>
        <span className="hint">{p.metric_name}</span>
      </div>
      <div className="stat-block">
        <span className="stat-label">原始 p / 全方案 BH q</span>
        <div className="big-num" style={{ fontSize: 18 }}>
          {fmtP(p.p_value)} / {fmtQ(p.q_value)}
        </div>
        <span className="hint">
          {p.bh_reject ? `q ≤ α=${alpha}，校正后仍显著` : `q > α=${alpha}，校正后失真`}
        </span>
      </div>
      <div className="stat-block">
        <span className="stat-label">MDE（80% 功效）</span>
        <div className="big-num" style={{ fontSize: 18 }}>{fmtPct(p.mde_required?.relative ?? null)}</div>
        <span className="hint">观测 lift {fmtSignedPct(p.lift)}</span>
      </div>
    </div>
  );
};
