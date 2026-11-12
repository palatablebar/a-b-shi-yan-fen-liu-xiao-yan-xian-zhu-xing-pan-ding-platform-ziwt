/** 报告导出与决策记录：MD/CSV 导出、报告预览、裁决记录、审计留痕。 */
import { useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useAsync } from '../hooks/useAsync';
import { usePageTitle } from '../hooks/usePageTitle';
import { listExperiments } from '../api/experiment';
import { listDecisions, createDecision } from '../api/decision';
import { fetchAuditLogs } from '../api/meta';
import { downloadReport, previewReport } from '../api/report';
import { useAuthStore } from '../stores/authStore';
import { can } from '../constants/roles';
import {
  DECISION_HINT,
  DECISION_LABEL,
  DECISION_OPTIONS,
  VERDICT_LABEL,
} from '../constants/enums';
import { fmtDateTime, fmtInt } from '../utils/format';
import { verdictTone } from '../utils/display';
import type { DecisionKind } from '../types/models';
import { SheetPanel } from '../components/common/SheetPanel';
import { RuledTable, type Column } from '../components/common/RuledTable';
import { StatusPill } from '../components/common/StatusPill';
import { VerdictStamp } from '../components/common/VerdictStamp';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorNote } from '../components/common/ErrorNote';
import { RequireRole } from '../components/common/RequireRole';
import { Annotation } from '../components/common/Annotation';
import { errorMessage } from '../utils/errorMessage';
import type { DecisionRecord } from '../types/models';

export const DecisionsPage = () => {
  usePageTitle('报告与决策');
  const role = useAuthStore((state) => state.user?.role);
  const experiments = useAsync(listExperiments, []);
  const decisions = useAsync(listDecisions, []);
  const [selectedExperiment, setSelectedExperiment] = useState<number>(0);
  const [preview, setPreview] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [decisionKind, setDecisionKind] = useState<DecisionKind>('continue');
  const [rationale, setRationale] = useState('');
  const [guardAck, setGuardAck] = useState(false);
  const [saving, setSaving] = useState(false);
  const audit = useAsync(() => (can(role, 'audit:read') ? fetchAuditLogs(20) : Promise.resolve([])), [role]);

  const decidables = (experiments.data ?? []).filter(
    (experiment) => experiment.latest_verdict && experiment.latest_verdict !== 'unreadable',
  );

  useEffect(() => {
    if (!selectedExperiment && decidables.length > 0) {
      setSelectedExperiment(decidables[0].id);
    }
  }, [decidables, selectedExperiment]);

  const loadPreview = async (experimentId: number) => {
    if (!experimentId) return;
    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const response = await previewReport(experimentId);
      setPreview(response.markdown);
    } catch (error) {
      setPreview(null);
      setPreviewError(errorMessage(error));
    } finally {
      setPreviewLoading(false);
    }
  };

  const submitDecision = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedExperiment) return;
    setSaving(true);
    setActionError(null);
    try {
      await createDecision(selectedExperiment, {
        decision: decisionKind,
        rationale: rationale.trim(),
        guard_ack: guardAck,
      });
      setRationale('');
      setGuardAck(false);
      decisions.reload();
      experiments.reload();
    } catch (error) {
      setActionError(errorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const decisionColumns: Column<DecisionRecord>[] = [
    {
      key: 'experiment',
      label: '实验',
      render: (row) => (
        <span>
          <strong>{row.experiment_name ?? '—'}</strong>
          <span className="hint mono" style={{ marginLeft: 6 }}>
            {row.experiment_code ?? ''}
          </span>
        </span>
      ),
    },
    {
      key: 'run',
      label: '批次',
      render: (row) => <span className="hint mono">{row.run_code ?? '—'}</span>,
    },
    {
      key: 'verdict',
      label: '结论',
      align: 'center',
      render: (row) =>
        row.verdict ? <VerdictStamp verdict={row.verdict} animate={false} /> : <span className="hint">—</span>,
    },
    {
      key: 'decision',
      label: '裁决',
      align: 'center',
      render: (row) => (
        <StatusPill
          tone={
            row.decision === 'ship' ? 'ok' : row.decision === 'kill' ? 'fail' : 'warn'
          }
        >
          {DECISION_LABEL[row.decision]}
        </StatusPill>
      ),
    },
    {
      key: 'rationale',
      label: '理由',
      render: (row) => <span style={{ fontSize: 12 }}>{row.rationale}</span>,
    },
    {
      key: 'reviewer',
      label: '复核人',
      render: (row) => <span className="hint mono">{row.reviewer}</span>,
    },
    {
      key: 'guard',
      label: '守卫确认',
      align: 'center',
      render: (row) => (row.guard_ack ? <span className="pill ok">已确认</span> : <span className="pill">未确认</span>),
    },
    {
      key: 'created',
      label: '记录时间',
      align: 'right',
      render: (row) => <span className="hint mono">{fmtDateTime(row.created_at)}</span>,
    },
  ];

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="kicker">DECISIONS / 04</div>
          <h1>报告导出与决策记录</h1>
          <p className="sub">
            结论可读才能裁决：上线 / 继续观察 / 下线，写清理由并留痕；报告支持 Markdown 与 CSV。
          </p>
        </div>
        <div className="head-aside">
          <div>决策记录 {fmtInt(decisions.data?.length ?? null)} 条</div>
          <div>可裁决实验 {fmtInt(decidables.length)} 个</div>
        </div>
      </div>

      <div className="split split-2">
        <SheetPanel
          title="报告预览"
          index="A"
          note={selectedExperiment ? `experiment #${selectedExperiment}` : '选择实验'}
          actions={
            <select
              className="btn small"
              value={selectedExperiment || ''}
              onChange={(event) => setSelectedExperiment(Number(event.target.value))}
            >
              <option value="">选择实验…</option>
              {(experiments.data ?? []).map((experiment) => (
                <option key={experiment.id} value={experiment.id}>
                  {experiment.code} · {experiment.name}
                </option>
              ))}
            </select>
          }
        >
          <div className="row" style={{ marginBottom: 8 }}>
            <button
              className="btn small"
              onClick={() => void loadPreview(selectedExperiment)}
              disabled={!selectedExperiment || previewLoading}
            >
              {previewLoading ? '生成中…' : '生成预览'}
            </button>
            <button
              className="btn small"
              disabled={!selectedExperiment}
              onClick={() => {
                setActionError(null);
                void downloadReport(selectedExperiment, 'md').catch((error) =>
                  setActionError(errorMessage(error)),
                );
              }}
            >
              下载 MD
            </button>
            <button
              className="btn small"
              disabled={!selectedExperiment}
              onClick={() => {
                setActionError(null);
                void downloadReport(selectedExperiment, 'csv').catch((error) =>
                  setActionError(errorMessage(error)),
                );
              }}
            >
              下载 CSV
            </button>
          </div>
          {previewError ? (
            <ErrorNote message={previewError} onRetry={() => void loadPreview(selectedExperiment)} />
          ) : preview ? (
            <pre className="report-preview">{preview}</pre>
          ) : (
            <EmptyState title="还没有生成预览">
              选择实验后点「生成预览」：报告包含 SRM 分流校验、指标对比（lift / CI / p / MDE）、
              分层 BH 校正、守卫指标与结论理由；下载按钮直接导出后端生成的文件。
            </EmptyState>
          )}
          {actionError ? (
            <div className="annotation" role="alert">
              <span className="annotation-label">错误</span>
              {actionError}
            </div>
          ) : null}
        </SheetPanel>

        <SheetPanel title="落决策记录" index="B" note="仅增长负责人（admin）">
          <RequireRole
            action="decisions:write"
            fallback={
              <div className="empty">
                <h4>当前角色只读</h4>
                <p>
                  产品经理{role === 'pm' ? '' : '/分析师'}可以查看结论与导出报告，
                  但裁决只能由增长负责人（admin）落记录；后端对越权写操作返回 403。
                </p>
                <p className="hint" style={{ marginTop: 8 }}>
                  {role === 'pm' ? '下一步：把报告导出给增长负责人评审。' : '下一步：把分层异质性与样本量结论同步给增长负责人。'}
                </p>
              </div>
            }
          >
            <form className="stack" onSubmit={submitDecision}>
              <div className="field">
                <label htmlFor="decision-experiment">实验（仅列出结论可读项）</label>
                <select
                  id="decision-experiment"
                  value={selectedExperiment || ''}
                  onChange={(event) => setSelectedExperiment(Number(event.target.value))}
                >
                  <option value="">选择实验…</option>
                  {decidables.map((experiment) => (
                    <option key={experiment.id} value={experiment.id}>
                      {experiment.code} · {experiment.name}（
                      {experiment.latest_verdict ? VERDICT_LABEL[experiment.latest_verdict] : '—'}）
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="decision-kind">裁决</label>
                <select
                  id="decision-kind"
                  value={decisionKind}
                  onChange={(event) => setDecisionKind(event.target.value as DecisionKind)}
                >
                  {DECISION_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {DECISION_LABEL[option]} — {DECISION_HINT[option]}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="decision-rationale">裁决理由（≥ 20 字）</label>
                <textarea
                  id="decision-rationale"
                  value={rationale}
                  onChange={(event) => setRationale(event.target.value)}
                  placeholder="写清依据：主指标效应、分层是否一致、守卫指标是否回归、后续计划"
                  minLength={20}
                  required
                />
              </div>
              <label className="hint" style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <input
                  type="checkbox"
                  checked={guardAck}
                  onChange={(event) => setGuardAck(event.target.checked)}
                />
                已人工复核守卫指标（客诉 / 工单）无回归
              </label>
              {actionError ? (
                <div className="annotation" role="alert">
                  <span className="annotation-label">错误</span>
                  {actionError}
                </div>
              ) : null}
              <div className="row">
                <button className="btn ink" type="submit" disabled={saving || !selectedExperiment}>
                  {saving ? '写入中…' : '落决策记录'}
                </button>
                <span className="hint">结论为 unreadable 的实验不会出现在上方列表（后端也会 423 拒绝）。</span>
              </div>
            </form>
          </RequireRole>
        </SheetPanel>
      </div>

      <div style={{ marginTop: 16 }}>
        <SheetPanel
          title="决策记录"
          index="C"
          note="一次裁决一行，含结论印章与理由"
          dense
          actions={<button className="btn ghost small" onClick={decisions.reload}>刷新</button>}
        >
          {decisions.loading && !decisions.data ? (
            <p className="loading-note">正在读取决策记录…</p>
          ) : decisions.error ? (
            <ErrorNote message={decisions.error} onRetry={decisions.reload} />
          ) : (decisions.data ?? []).length === 0 ? (
            <EmptyState title="还没有决策记录">
              分析批次结论为 pass / warn 时，增长负责人可以在这里落决策；unreadable（如 SRM 失衡）会被锁定拒绝。
            </EmptyState>
          ) : (
            <RuledTable
              columns={decisionColumns}
              rows={decisions.data ?? []}
              rowKey={(row) => row.id}
            />
          )}
        </SheetPanel>
      </div>

      {can(role, 'audit:read') ? (
        <div style={{ marginTop: 16 }}>
          <SheetPanel title="审计留痕" index="D" note="写操作按请求记录" dense>
            {audit.loading ? (
              <p className="loading-note">正在读取审计…</p>
            ) : (
              <RuledTable
                columns={[
                  { key: 'time', label: '时间', render: (row) => <span className="hint mono">{fmtDateTime(row.created_at)}</span> },
                  { key: 'actor', label: '操作人', render: (row) => <span className="mono">{row.actor_email}</span> },
                  { key: 'action', label: '动作', render: (row) => row.action },
                  { key: 'status', label: '状态码', align: 'right', render: (row) => <span className="mono">{row.status_code}</span> },
                  { key: 'path', label: '路径', render: (row) => <span className="hint mono">{row.method} {row.path}</span> },
                ]}
                rows={audit.data ?? []}
                rowKey={(row) => row.id}
                empty={<p className="hint">暂无审计记录：触发一次分析或登录后即可看到。</p>}
              />
            )}
          </SheetPanel>
        </div>
      ) : null}

      <p className="hint" style={{ marginTop: 12 }}>
        提示：结论为 warn 的实验建议裁决「继续观察」；pass 才能「上线」；守卫指标显著变差将直接判 fail。
        {' '}查看全部批次请前往 <Link className="inline-link" to="/runs">分析批次</Link>。
      </p>
    </div>
  );
};
