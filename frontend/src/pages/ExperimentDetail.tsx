/** 实验详情：分流校验 + 指标对比 + 守卫指标 + 跑分析。 */
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getRun } from '../api/run';
import { useAsync } from '../hooks/useAsync';
import { usePageTitle } from '../hooks/usePageTitle';
import { useRunStore } from '../stores/runStore';
import type { RunDetail } from '../types/models';
import { EXPERIMENT_STATUS_LABEL, SRM_LABEL } from '../constants/enums';
import { srmTone, statusTone, verdictTone } from '../utils/display';
import { fmtDateTime, fmtInt, fmtLift, fmtP } from '../utils/format';
import { SheetPanel } from '../components/common/SheetPanel';
import { StatusPill } from '../components/common/StatusPill';
import { VerdictStamp } from '../components/common/VerdictStamp';
import { StepTicks } from '../components/common/StepTicks';
import { Annotation } from '../components/common/Annotation';
import { RequireRole } from '../components/common/RequireRole';
import { StatBlock } from '../components/common/StatBlock';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorNote } from '../components/common/ErrorNote';
import { MetricNum } from '../components/common/MetricNum';
import { SrmBlock } from '../components/business/SrmBlock';
import { VariantSplit } from '../components/business/VariantSplit';
import { MetricContrastTable } from '../components/business/MetricContrastTable';
import { GuardGrid } from '../components/business/GuardGrid';
import { downloadReport } from '../api/report';
import { errorMessage } from '../utils/errorMessage';

export const ExperimentDetailPage = () => {
  const params = useParams();
  const experimentId = Number(params.experimentId);
  const detail = useAsync(() => import('../api/experiment').then((mod) => mod.getExperiment(experimentId)), [experimentId]);
  const latestRunId = detail.data?.latest_run?.id ?? null;
  const runDetail = useAsync<RunDetail | null>(
    () => (latestRunId ? getRun(latestRunId) : Promise.resolve(null)),
    [latestRunId],
  );
  const trigger = useRunStore((state) => state.trigger);
  const pollUntilDone = useRunStore((state) => state.pollUntilDone);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  usePageTitle(detail.data ? `${detail.data.code} 实验详情` : '实验详情');

  const experiment = detail.data;
  const run = runDetail.data;
  useEffect(() => {
    if (run && latestRunId) {
      // 批次完成时刷新实验摘要（结论/锁定状态）
    }
  }, [run, latestRunId]);

  if (detail.loading && !experiment) {
    return <p className="loading-note">正在读取实验页…</p>;
  }
  if (detail.error || !experiment) {
    return <ErrorNote message={detail.error ?? '实验不存在'} onRetry={detail.reload} />;
  }

  const srm = experiment.srm_snapshot ?? experiment.latest_run?.srm ?? null;
  const latest = experiment.latest_run;
  const broken = srm?.verdict === 'detected';
  const stepCurrent = !latest ? 1 : latest.status === 'succeeded' ? (experiment.decision ? 5 : 4) : 2;
  const primaryComparison = run?.metrics?.find((entry) => entry.family === 'primary') ?? null;

  const onTrigger = async () => {
    setBusy(true);
    setActionError(null);
    try {
      const created = await trigger(experiment.id);
      const finished = await pollUntilDone(created.id);
      if (finished?.status === 'failed') {
        setActionError(finished.error ?? '分析失败');
      }
      detail.reload();
      runDetail.reload();
    } catch (error) {
      setActionError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="kicker">
            EXPERIMENT / {experiment.code.toUpperCase()}
          </div>
          <h1>{experiment.name}</h1>
          <p className="sub">
            {experiment.owner_name} · {experiment.start_date ?? '—'} → {experiment.end_date ?? '—'} · 主指标{' '}
            {experiment.primary_metric?.name ?? '未设置'}
          </p>
        </div>
        <div className="head-aside">
          <StatusPill tone={statusTone(experiment.status)}>
            {EXPERIMENT_STATUS_LABEL[experiment.status]}
          </StatusPill>
          <div>
            α={experiment.alpha} · SRM 阈值 p&lt;{experiment.srm_threshold} · 每臂下限{' '}
            {experiment.min_sample_per_arm}
          </div>
          <div>分桶 {fmtInt(experiment.assignment_total)} 条</div>
        </div>
      </div>

      <StepTicks current={stepCurrent} broken={broken} />

      <div className="split split-2">
        <div className="stack">
          <SheetPanel
            title="分流校验 SRM"
            index="A"
            note={srm ? `曝光总数 ${fmtInt(srm.total)}` : '尚无校验结果'}
            actions={
              srm ? <StatusPill tone={srmTone(srm.verdict)}>{SRM_LABEL[srm.verdict]}</StatusPill> : null
            }
          >
            <SrmBlock srm={srm} variantNames={experiment.variants.map((variant) => variant.name)} />
          </SheetPanel>

          <SheetPanel title="变体分桶" index="B" note="用户级分桶 · 曝光次数口径">
            <VariantSplit
              variants={experiment.variants}
              expected={experiment.variants.map((variant) => variant.traffic_allocation)}
            />
          </SheetPanel>
        </div>

        <div className="stack">
          <SheetPanel title="判定摘要" index="C" note={latest ? latest.run_code : '尚未跑分析'}>
            <div className="row-between" style={{ marginBottom: 10 }}>
              <VerdictStamp verdict={latest?.verdict ?? null} large />
              {latest ? (
                <span className="hint mono">
                  {latest.finished_at ? fmtDateTime(latest.finished_at) : latest.status}
                </span>
              ) : null}
            </div>
            <div className="split split-3">
              <StatBlock
                label="主指标 lift"
                value={<MetricNum value={latest?.primary_lift ?? null} kind="lift" />}
                foot={experiment.primary_metric?.name}
              />
              <StatBlock
                label="p 值"
                value={<MetricNum value={latest?.primary_p_value ?? null} kind="p" />}
                foot={`α=${experiment.alpha}`}
              />
              <StatBlock
                label="SRM p"
                value={<MetricNum value={srm?.p_value ?? null} kind="p" />}
                foot={broken ? '已锁定结论' : '分流正常'}
                tone={broken ? 'red' : 'default'}
              />
            </div>
            {latest?.verdict_reasons?.length ? (
              <ul className="reason-list" style={{ marginTop: 8 }}>
                {latest.verdict_reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            ) : (
              <p className="hint">尚无判定理由：触发一次分析后写入。</p>
            )}
            {actionError ? (
              <div className="annotation" role="alert">
                <span className="annotation-label">错误</span>
                {actionError}
              </div>
            ) : null}
            <div className="row" style={{ marginTop: 12 }}>
              <RequireRole action="runs:trigger">
                <button className="btn ink small" onClick={onTrigger} disabled={busy}>
                  {busy ? '分析中…' : '跑一次分析'}
                </button>
              </RequireRole>
              <Link className="btn small" to={`/segments?experimentId=${experiment.id}`}>
                分层分析
              </Link>
              <button
                className="btn small"
                onClick={() => {
                  void downloadReport(experiment.id, 'md').catch((error) =>
                    setActionError(errorMessage(error)),
                  );
                }}
              >
                导出 MD
              </button>
              <button
                className="btn small"
                onClick={() => {
                  void downloadReport(experiment.id, 'csv').catch((error) =>
                    setActionError(errorMessage(error)),
                  );
                }}
              >
                导出 CSV
              </button>
            </div>
            <RequireRole
              action="runs:trigger"
              fallback={<p className="hint" style={{ marginTop: 8 }}>产品经理为只读角色：可查看结论与导出报告，不能触发分析或裁决。</p>}
            >
              <span />
            </RequireRole>
            {experiment.notes ? <Annotation>{experiment.notes}</Annotation> : null}
            {experiment.decision ? (
              <div className="annotation" style={{ background: 'var(--ok-wash)', borderColor: 'var(--ok)', color: 'var(--ok)' }}>
                <span className="annotation-label" style={{ color: 'var(--ok)' }}>决策</span>
                {experiment.decision.decision === 'ship' ? '上线' : experiment.decision.decision === 'kill' ? '下线' : '继续观察'}
                {' — '}
                {experiment.decision.rationale}
              </div>
            ) : null}
          </SheetPanel>
        </div>
      </div>

      <div style={{ marginTop: 16 }}>
        <SheetPanel
          title="指标对比"
          index="D"
          note={run ? `${run.run_code} · 用户级样本` : '等待分析批次'}
          actions={
            run ? (
              <Link className="inline-link" to="/runs">
                查看完整批次 →
              </Link>
            ) : null
          }
        >
          {run?.metrics?.length ? (
            <MetricContrastTable metrics={run.metrics} alpha={experiment.alpha} />
          ) : latest ? (
            <p className="loading-note">正在读取批次明细…</p>
          ) : (
            <EmptyState
              title="还没有分析批次"
              action={
                <RequireRole action="runs:trigger">
                  <button className="btn small ink" onClick={onTrigger} disabled={busy}>
                    触发首次分析
                  </button>
                </RequireRole>
              }
            >
              具备 admin / analyst 角色时可以触发分析：后端会在 Celery worker 里真算 SRM 卡方、
              两比例 z（或 Welch t）、分层 BH 与守卫指标回归，结果落库后本页自动刷新。
            </EmptyState>
          )}
        </SheetPanel>
      </div>

      <div style={{ marginTop: 16 }} className="split split-2">
        <SheetPanel title="守卫指标" index="E" note="显著变差 → 结论降级 fail">
          <GuardGrid guard={run?.guard ?? null} />
        </SheetPanel>
        <SheetPanel title="实验假设与口径" index="F" note={experiment.created_by}>
          <p style={{ fontSize: 14 }}>{experiment.hypothesis || '未填写实验假设。'}</p>
          <p className="hint" style={{ marginTop: 8 }}>
            {experiment.description || '无补充描述'}
          </p>
          <dl className="kv" style={{ marginTop: 12 }}>
            <dt>守卫指标</dt>
            <dd>{experiment.guard_metrics.map((metric) => metric.name).join('、') || '未配置'}</dd>
            <dt>创建人</dt>
            <dd className="mono">{experiment.created_by || '—'}</dd>
            <dt>最近更新</dt>
            <dd className="mono">{fmtDateTime(experiment.updated_at)}</dd>
          </dl>
        </SheetPanel>
      </div>
      {run ? (
        <p className="hint" style={{ marginTop: 12 }}>
          最近批次 {run.run_code}：SRM p={fmtP(run.srm?.p_value ?? null)}，主指标 lift=
          {fmtLift(run.metrics?.find((entry) => entry.family === 'primary')?.stat.lift ?? null)}，
          结论 {run.verdict ?? '—'}。
        </p>
      ) : null}
    </div>
  );
};
