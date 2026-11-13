/** 分析批次：批次列表 + 单批次完整结果（效应量 / CI / 分层 BH / 守卫 / 结论）。 */
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAsync } from '../hooks/useAsync';
import { usePageTitle } from '../hooks/usePageTitle';
import { listRuns, getRun } from '../api/run';
import { useRunStore } from '../stores/runStore';
import { guardTone, runTone, srmTone, verdictTone } from '../utils/display';
import {
  RUN_STATUS_LABEL,
  SRM_LABEL,
  VERDICT_LABEL,
} from '../constants/enums';
import { fmtDateTime, fmtInt, fmtLift, fmtP, fmtPct, fmtRateOrMean } from '../utils/format';
import { SheetPanel } from '../components/common/SheetPanel';
import { StatusPill } from '../components/common/StatusPill';
import { VerdictStamp } from '../components/common/VerdictStamp';
import { RuledTable, type Column } from '../components/common/RuledTable';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorNote } from '../components/common/ErrorNote';
import { RequireRole } from '../components/common/RequireRole';
import { Annotation } from '../components/common/Annotation';
import { SrmBlock } from '../components/business/SrmBlock';
import { MetricContrastTable } from '../components/business/MetricContrastTable';
import { GuardGrid } from '../components/business/GuardGrid';
import { BhTable } from '../components/business/BhTable';
import { MultiArmBoard } from '../components/business/MultiArmBoard';
import type { ComparisonRow, RunDetail, RunSummary } from '../types/models';
import { useAuthStore } from '../stores/authStore';
import { errorMessage } from '../utils/errorMessage';

const FAMILY_LABEL: Record<string, string> = {
  primary: '主指标',
  guard: '守卫指标',
  secondary: '辅助指标',
  strata: '分层',
};

export const RunsPage = () => {
  usePageTitle('分析批次');
  const runs = useAsync(listRuns, []);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const detail = useAsync(
    () => (selectedId ? getRun(selectedId) : Promise.resolve(null)),
    [selectedId],
  );
  const trigger = useRunStore((state) => state.trigger);
  const pollUntilDone = useRunStore((state) => state.pollUntilDone);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const alpha = 0.05;

  useEffect(() => {
    if (selectedId === null && (runs.data ?? []).length > 0) {
      setSelectedId(runs.data![0].id);
    }
  }, [runs.data, selectedId]);

  const selectedSummary = useMemo(
    () => (runs.data ?? []).find((run) => run.id === selectedId) ?? null,
    [runs.data, selectedId],
  );
  const run = detail.data;

  const onRerun = async () => {
    if (!selectedSummary) return;
    setBusy(true);
    setActionError(null);
    try {
      const created = await trigger(selectedSummary.experiment_id);
      const finished = await pollUntilDone(created.id);
      runs.reload();
      if (finished && finished.status === 'succeeded') setSelectedId(finished.id);
      else if (finished?.status === 'failed') setActionError(finished.error ?? '分析失败');
    } catch (error) {
      setActionError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };

  const comparisonColumns: Column<ComparisonRow>[] = [
    { key: 'label', label: '检验项', render: (row) => row.label },
    {
      key: 'family',
      label: '族',
      render: (row) => <span className="hint">{FAMILY_LABEL[row.family] ?? row.family}</span>,
    },
    {
      key: 'p',
      label: 'p 值',
      align: 'right',
      render: (row) => <span className={row.p_value < alpha ? 'sig-text' : ''}>{fmtP(row.p_value)}</span>,
    },
    {
      key: 'q',
      label: 'q 值（全量 BH）',
      align: 'right',
      render: (row) => <span className={row.reject ? 'sig-text' : ''}>{fmtP(row.q_value)}</span>,
    },
    {
      key: 'rank',
      label: '秩',
      align: 'right',
      render: (row) => <span className="mono">{row.rank ?? '—'}</span>,
    },
    {
      key: 'reject',
      label: 'BH 后显著',
      align: 'center',
      render: (row) =>
        row.reject ? <span className="pill ok">显著</span> : <span className="pill">不显著</span>,
    },
  ];

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="kicker">RUNS / 02</div>
          <h1>分析批次与显著性判定</h1>
          <p className="sub">
            批次由 Celery worker 真算：SRM 卡方 → 指标检验（z / Welch t）→ 分层 BH → 守卫回归 → 固定规则结论。
          </p>
        </div>
        <div className="head-aside">
          <div>共 {fmtInt(runs.data?.length ?? null)} 个批次</div>
          <div>α=0.05 · MDE 按 80% 功效</div>
        </div>
      </div>

      <div className="runs-layout">
        <div className="stack">
          <SheetPanel
            title="批次列表"
            index="A"
            note="点击查看判定明细"
            dense
            actions={<button className="btn ghost small" onClick={runs.reload}>刷新</button>}
          >
            {runs.loading && !runs.data ? (
              <p className="loading-note">正在读取批次…</p>
            ) : runs.error ? (
              <ErrorNote message={runs.error} onRetry={runs.reload} />
            ) : (runs.data ?? []).length === 0 ? (
              <EmptyState title="还没有分析批次">到实验详情页触发一次分析，批次会出现在这里。</EmptyState>
            ) : (
              <div className="run-list">
                {(runs.data ?? []).map((summary) => (
                  <button
                    key={summary.id}
                    className={`run-item${selectedId === summary.id ? ' active' : ''}`}
                    onClick={() => setSelectedId(summary.id)}
                  >
                    <div className="row-between">
                      <span className="run-code">{summary.run_code}</span>
                      <VerdictStamp verdict={summary.verdict} animate={false} />
                    </div>
                    <div className="row-between" style={{ marginTop: 4 }}>
                      <span className="hint">
                        {summary.experiment_name ?? summary.experiment_code ?? '—'}
                      </span>
                      <StatusPill tone={runTone(summary.status)}>
                        {RUN_STATUS_LABEL[summary.status]}
                      </StatusPill>
                    </div>
                    <div className="hint mono" style={{ marginTop: 2 }}>
                      lift {fmtLift(summary.primary_lift)} · p {fmtP(summary.primary_p_value)} ·{' '}
                      {fmtDateTime(summary.created_at)}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </SheetPanel>

          {selectedSummary ? (
            <SheetPanel title="批次操作" index="B" note={selectedSummary.experiment_code ?? ''}>
              <div className="row">
                <RequireRole action="runs:trigger">
                  <button className="btn ink small" onClick={onRerun} disabled={busy}>
                    {busy ? '重新分析中…' : '重跑该实验分析'}
                  </button>
                </RequireRole>
                <Link className="btn small" to={`/experiments/${selectedSummary.experiment_id}`}>
                  打开实验详情
                </Link>
                <Link className="btn small" to={`/segments?experimentId=${selectedSummary.experiment_id}`}>
                  分层下钻
                </Link>
              </div>
              {actionError ? (
                <div className="annotation" role="alert">
                  <span className="annotation-label">错误</span>
                  {actionError}
                </div>
              ) : null}
            </SheetPanel>
          ) : null}
        </div>

        <div className="stack">
          {detail.loading && !run ? (
            <p className="loading-note">正在读取批次明细…</p>
          ) : detail.error ? (
            <ErrorNote message={detail.error} onRetry={detail.reload} />
          ) : !run ? (
            <SheetPanel title="批次明细" index="C">
              <EmptyState title="选择左侧批次">每个批次都保存完整的 SRM、指标、分层与判定理由。</EmptyState>
            </SheetPanel>
          ) : (
            <RunResult run={run} alpha={alpha} />
          )}
        </div>
      </div>
    </div>
  );
};

const RunResult = ({ run, alpha }: { run: RunDetail; alpha: number }) => {
  const role = useAuthStore((state) => state.user?.role);
  const primary = run.metrics?.find((entry) => entry.family === 'primary') ?? null;
  const strata = run.strata;
  const kind = primary?.kind ?? 'ratio';
  const guardBlocked = run.guard?.regression;
  const multiArm = run.params?.multi_arm === true || (run.arms?.length ?? 0) > 0;

  if (multiArm && run.arms?.length) {
    return (
      <div className="stack">
        <SheetPanel
          title="判定结论（多方案共同对照）"
          index="C"
          note={run.run_code}
          actions={<VerdictStamp verdict={run.verdict} large />}
        >
          <ul className="reason-list">
            {(run.verdict_reasons ?? []).map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
          <dl className="kv" style={{ marginTop: 10 }}>
            <dt>触发人</dt>
            <dd className="mono">{run.triggered_by}</dd>
            <dt>处理方案数</dt>
            <dd className="mono">
              {run.arms.length} 个（共同对照：{run.arms[0].control_variant.name}）
            </dd>
            <dt>统一 BH family</dt>
            <dd className="mono">m={run.comparisons?.length ?? 0} · α={alpha}</dd>
            <dt>完成时间</dt>
            <dd className="mono">{fmtDateTime(run.finished_at)}</dd>
          </dl>
          {run.locked ? (
            <Annotation>
              分流失衡（SRM）或样本不足 → 结论锁定 unreadable；此时「报告与决策」页会拒绝创建决策记录。
            </Annotation>
          ) : null}
          <Annotation>
            可上线状态 ship_state：只有 ship_eligible 的方案可以放量；watch_only 仅可继续观察；
            blocked（守卫生效或全方案 BH 校正后失真）的方案不能被当成赢家。
          </Annotation>
        </SheetPanel>

        <MultiArmBoard run={run} alpha={alpha} />

        {run.status === 'succeeded' && run.verdict !== 'unreadable' ? (
          <p className="hint">
            下一步：到{' '}
            <Link className="inline-link" to="/decisions">
              报告与决策
            </Link>{' '}
            落决策记录并导出 MD / CSV。
          </p>
        ) : null}
      </div>
    );
  }

  return (
    <div className="stack">
      <SheetPanel
        title="判定结论"
        index="C"
        note={run.run_code}
        actions={<VerdictStamp verdict={run.verdict} large />}
      >
        <div className="split split-3" style={{ marginBottom: 10 }}>
          <div className="stat-block">
            <span className="stat-label">主指标 lift</span>
            <div className="big-num">{fmtLift(primary?.stat.lift ?? null)}</div>
            <span className="hint">
              {fmtRateOrMean(primary?.control_value ?? null, kind)} →{' '}
              {fmtRateOrMean(primary?.treat_value ?? null, kind)}
            </span>
          </div>
          <div className="stat-block">
            <span className="stat-label">p 值 / α</span>
            <div className="big-num">{fmtP(primary?.stat.p_value ?? null)}</div>
            <span className="hint">
              {primary && primary.stat.p_value < alpha ? '显著' : '未达显著'} · α={alpha}
            </span>
          </div>
          <div className="stat-block">
            <span className="stat-label">MDE（80% 功效）</span>
            <div className="big-num">{fmtPct(primary?.stat.mde_required?.relative ?? null)}</div>
            <span className="hint">
              观测效应 {primary?.stat.lift !== null ? fmtLift(primary?.stat.lift ?? null) : '—'}
            </span>
          </div>
        </div>
        <ul className="reason-list">
          {(run.verdict_reasons ?? []).map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
        <dl className="kv" style={{ marginTop: 10 }}>
          <dt>触发人</dt>
          <dd className="mono">{run.triggered_by}</dd>
          <dt>样本（对照 / 实验）</dt>
          <dd className="mono">
            {fmtInt(primary?.stat.control_n ?? null)} / {fmtInt(primary?.stat.treat_n ?? null)} 用户
          </dd>
          <dt>曝光（对照 / 实验）</dt>
          <dd className="mono">
            {fmtInt(run.srm?.observed?.[0] ?? null)} / {fmtInt(run.srm?.observed?.[1] ?? null)} 次
          </dd>
          <dt>结论锁定</dt>
          <dd>{run.locked ? '是（不可读，禁止落决策）' : '否'}</dd>
          <dt>完成时间</dt>
          <dd className="mono">{fmtDateTime(run.finished_at)}</dd>
        </dl>
        {run.status === 'failed' ? (
          <Annotation>批次失败：{run.error ?? '未知错误'}。请检查 worker 日志后重跑。</Annotation>
        ) : null}
        {run.locked ? (
          <Annotation>
            分流失衡（SRM）或样本不足 → 结论锁定 unreadable；此时「报告与决策」页会拒绝创建决策记录。
          </Annotation>
        ) : null}
        {guardBlocked ? <Annotation>守卫指标显著变差，按固定规则结论降级为 fail。</Annotation> : null}
        {role === 'pm' ? (
          <p className="hint">产品经理视角：结论与报告只读，触发/裁决按钮不可用。</p>
        ) : null}
      </SheetPanel>

      <SheetPanel title="分流校验" index="D" note={run.srm ? `曝光 ${fmtInt(run.srm.total)}` : ''}>
        <SrmBlock srm={run.srm} />
      </SheetPanel>

      <SheetPanel title="指标对比" index="E" note="两次检验均在后端完成">
        {run.metrics?.length ? <MetricContrastTable metrics={run.metrics} alpha={alpha} /> : <p className="hint">无指标数据。</p>}
      </SheetPanel>

      <SheetPanel title="守卫指标" index="F" note="显著变差即降级">
        <GuardGrid guard={run.guard} />
      </SheetPanel>

      {strata ? (
        <>
          <SheetPanel
            title="分层 BH 校正"
            index="G"
            note={`m=${strata.family.m} · 原始显著 ${strata.summary.raw_significant} / 校正后 ${strata.summary.bh_significant}`}
          >
            <BhTable strata={strata} kind={kind} />
          </SheetPanel>
          <SheetPanel title="全量 BH（所有检验合并一个族）" index="H" dense>
            <RuledTable
              columns={[
                { key: 'label', label: '检验项', render: (row) => row.label },
                {
                  key: 'family',
                  label: '族',
                  render: (row) => <span className="hint">{FAMILY_LABEL[row.family] ?? row.family}</span>,
                },
                {
                  key: 'p',
                  label: 'p 值',
                  align: 'right',
                  render: (row) => <span className={row.p_value < alpha ? 'sig-text' : ''}>{fmtP(row.p_value)}</span>,
                },
                {
                  key: 'q',
                  label: 'q 值',
                  align: 'right',
                  render: (row) => <span className={row.reject ? 'sig-text' : ''}>{fmtP(row.q_value)}</span>,
                },
                {
                  key: 'reject',
                  label: 'BH 后',
                  align: 'center',
                  render: (row) =>
                    row.reject ? <span className="pill ok">显著</span> : <span className="pill">不显著</span>,
                },
              ]}
              rows={run.comparisons ?? []}
              rowKey={(row) => row.label}
            />
          </SheetPanel>
        </>
      ) : null}

      {run.status === 'succeeded' && run.verdict !== 'unreadable' ? (
        <p className="hint">
          下一步：到{' '}
          <Link className="inline-link" to="/decisions">
            报告与决策
          </Link>{' '}
          落决策记录并导出 MD / CSV。
        </p>
      ) : null}
    </div>
  );
};
