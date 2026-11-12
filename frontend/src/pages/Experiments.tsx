/** 实验索引：状态筛选、分流台账、新建实验（admin/analyst）。 */
import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAsync } from '../hooks/useAsync';
import { usePageTitle } from '../hooks/usePageTitle';
import { listExperiments, createExperiment } from '../api/experiment';
import { listMetrics } from '../api/metric';
import type { ExperimentStatus, ExperimentSummary, Metric } from '../types/models';
import { EXPERIMENT_STATUS_LABEL, SRM_LABEL, VERDICT_LABEL } from '../constants/enums';
import { statusTone, srmTone, verdictTone } from '../utils/display';
import { fmtDate, fmtInt, fmtP, fmtSignedPct } from '../utils/format';
import { SheetPanel } from '../components/common/SheetPanel';
import { RuledTable, type Column } from '../components/common/RuledTable';
import { StatusPill } from '../components/common/StatusPill';
import { VerdictStamp } from '../components/common/VerdictStamp';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorNote } from '../components/common/ErrorNote';
import { RequireRole } from '../components/common/RequireRole';
import { Annotation } from '../components/common/Annotation';

type FilterKey = 'all' | ExperimentStatus;

const FILTERS: Array<{ key: FilterKey; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'running', label: '进行中' },
  { key: 'analyzing', label: '待处置' },
  { key: 'decided', label: '已裁决' },
  { key: 'draft', label: '草稿' },
];

export const ExperimentsPage = () => {
  usePageTitle('实验索引');
  const navigate = useNavigate();
  const experiments = useAsync(listExperiments, []);
  const metrics = useAsync(listMetrics, [], true);
  const [filter, setFilter] = useState<FilterKey>('all');
  const [showCreate, setShowCreate] = useState(false);
  const [saving, setSaving] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const rows = useMemo(() => {
    const items = experiments.data ?? [];
    return filter === 'all' ? items : items.filter((item) => item.status === filter);
  }, [experiments.data, filter]);

  const counts = useMemo(() => {
    const items = experiments.data ?? [];
    return {
      all: items.length,
      running: items.filter((item) => item.status === 'running').length,
      analyzing: items.filter((item) => item.status === 'analyzing').length,
      decided: items.filter((item) => item.status === 'decided').length,
      draft: items.filter((item) => item.status === 'draft').length,
    } as Record<FilterKey, number>;
  }, [experiments.data]);

  const columns: Column<ExperimentSummary>[] = [
    {
      key: 'idx',
      label: 'No.',
      width: '44px',
      render: (_row, index) => (
        <span className="mono" style={{ color: 'var(--red)' }}>
          {String(index + 1).padStart(2, '0')}
        </span>
      ),
    },
    {
      key: 'name',
      label: '实验 / 编号',
      render: (row) => (
        <div>
          <strong>{row.name}</strong>
          <div className="hint mono" style={{ marginTop: 2 }}>
            {row.code}
          </div>
        </div>
      ),
    },
    {
      key: 'metric',
      label: '主指标',
      render: (row) => <span className="hint">{row.primary_metric_name ?? '未设置'}</span>,
    },
    {
      key: 'status',
      label: '状态',
      render: (row) => (
        <StatusPill tone={statusTone(row.status)}>{EXPERIMENT_STATUS_LABEL[row.status]}</StatusPill>
      ),
    },
    {
      key: 'assignments',
      label: '分桶',
      align: 'right',
      render: (row) => <span className="mono">{fmtInt(row.assignments)}</span>,
    },
    {
      key: 'srm',
      label: 'SRM',
      align: 'center',
      render: (row) =>
        row.latest_srm ? (
          <StatusPill tone={srmTone(row.latest_srm)}>{SRM_LABEL[row.latest_srm]}</StatusPill>
        ) : (
          <span className="hint">待跑分析</span>
        ),
    },
    {
      key: 'verdict',
      label: '结论',
      align: 'center',
      render: (row) =>
        row.latest_verdict ? (
          <VerdictStamp verdict={row.latest_verdict} animate={false} />
        ) : (
          <span className="hint">—</span>
        ),
    },
    {
      key: 'run',
      label: '最近批次',
      align: 'right',
      render: (row) => (
        <span className="hint mono">{row.latest_run_at ? fmtDate(row.latest_run_at) : '—'}</span>
      ),
    },
    {
      key: 'window',
      label: '实验窗口',
      align: 'right',
      render: (row) => (
        <span className="hint mono">
          {row.start_date ?? '—'} → {row.end_date ?? '—'}
        </span>
      ),
    },
  ];

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="kicker">INDEX / 01</div>
          <h1>实验索引与分流台账</h1>
          <p className="sub">
            青柚出行 · 增长分析组 — 每个实验一行：分流比例、主指标、守卫指标与结论印章。
          </p>
        </div>
        <div className="head-aside">
          <div>
            共 {fmtInt(experiments.data?.length ?? null)} 个实验 · 分桶{' '}
            {fmtInt(experiments.data?.reduce((sum, item) => sum + item.assignments, 0) ?? null)} 条
          </div>
          <div>最近同步 {new Date().toLocaleTimeString('zh-CN')}</div>
        </div>
      </div>

      <div className="filter-tabs" role="tablist">
        {FILTERS.map((item) => (
          <button
            key={item.key}
            role="tab"
            aria-selected={filter === item.key}
            className={`filter-tab${filter === item.key ? ' active' : ''}`}
            onClick={() => setFilter(item.key)}
          >
            {item.label}
            <span className="count">{counts[item.key] ?? 0}</span>
          </button>
        ))}
        <span className="spacer" />
        <RequireRole action="experiments:write">
          <button className="btn small" onClick={() => setShowCreate((value) => !value)}>
            {showCreate ? '收起表单' : '新建实验'}
          </button>
        </RequireRole>
      </div>

      {showCreate ? (
        <CreateExperimentForm
          metrics={metrics.data ?? []}
          saving={saving}
          error={createError}
          onCancel={() => setShowCreate(false)}
          onSubmit={async (payload) => {
            setSaving(true);
            setCreateError(null);
            try {
              await createExperiment(payload);
              setShowCreate(false);
              experiments.reload();
            } catch (error) {
              setCreateError(error instanceof Error ? error.message : '创建实验失败');
            } finally {
              setSaving(false);
            }
          }}
        />
      ) : null}

      <SheetPanel
        title="实验台账"
        index="A"
        note={`${rows.length} 条记录 · 点击行进入详情`}
        dense
        actions={
          <button className="btn ghost small" onClick={experiments.reload}>
            刷新
          </button>
        }
      >
        {experiments.loading && !experiments.data ? (
          <p className="loading-note">正在读取台账…</p>
        ) : experiments.error ? (
          <ErrorNote message={experiments.error} onRetry={experiments.reload} />
        ) : rows.length === 0 ? (
          <EmptyState
            title="该状态下没有实验"
            action={<button className="btn small" onClick={() => setFilter('all')}>查看全部实验</button>}
          >
            切换上方筛选，或由增长负责人/分析师新建一个实验：填写主指标、守卫指标与两个变体。
          </EmptyState>
        ) : (
          <RuledTable
            columns={columns}
            rows={rows}
            rowKey={(row) => row.id}
            flagged={(row) => row.latest_srm === 'detected'}
            empty={<p>暂无实验。</p>}
          />
        )}
      </SheetPanel>

      <div style={{ marginTop: 12 }}>
        <Annotation>
          红色行 = 曝光口径分流校验触发 SRM。此时主指标/守卫指标的 p 值全部不可采信，
          结论锁定为 unreadable，必须先排查分流器与埋点重复上报。
        </Annotation>
        <p className="hint">
          想直接看结论？进入任一实验详情，或到{' '}
          <Link className="inline-link" to="/runs">
            分析批次
          </Link>{' '}
          查看每个批次的分层 BH 表与判定理由。
        </p>
      </div>
    </div>
  );
};

interface CreateFormProps {
  metrics: Metric[];
  saving: boolean;
  error: string | null;
  onCancel: () => void;
  onSubmit: (payload: Parameters<typeof createExperiment>[0]) => Promise<void>;
}

const CreateExperimentForm = ({ metrics, saving, error, onCancel, onSubmit }: CreateFormProps) => {
  const primaryOptions = metrics.filter((metric) => metric.role !== 'guard');
  const guardOptions = metrics.filter((metric) => metric.role === 'guard');
  const [code, setCode] = useState('exp_new_1109');
  const [name, setName] = useState('');
  const [owner, setOwner] = useState('青柚出行 · 增长分析组');
  const [hypothesis, setHypothesis] = useState('');
  const [primaryId, setPrimaryId] = useState<number>(primaryOptions[0]?.id ?? 0);
  const [guardIds, setGuardIds] = useState<number[]>(guardOptions.slice(0, 2).map((m) => m.id));
  const [notes, setNotes] = useState('');
  const [controlName, setControlName] = useState('分组 A · 对照');
  const [treatName, setTreatName] = useState('分组 B · 实验');

  return (
    <SheetPanel title="新建实验" index="N" note="仅 admin / analyst 可提交">
      <form
        className="stack"
        onSubmit={(event) => {
          event.preventDefault();
          void onSubmit({
            code,
            name: name || code,
            hypothesis,
            description: '',
            owner_name: owner,
            primary_metric_id: primaryId,
            guard_metric_ids: guardIds,
            secondary_metric_ids: [],
            notes,
            variants: [
              {
                code: 'control',
                name: controlName,
                traffic_allocation: 0.5,
                is_control: true,
                description: '对照组',
              },
              {
                code: 'treatment',
                name: treatName,
                traffic_allocation: 0.5,
                is_control: false,
                description: '实验组',
              },
            ],
          });
        }}
      >
        <div className="form-grid">
          <div className="field">
            <label htmlFor="new-code">实验编号</label>
            <input id="new-code" value={code} onChange={(event) => setCode(event.target.value)} required />
          </div>
          <div className="field">
            <label htmlFor="new-name">实验名称</label>
            <input
              id="new-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="例如：首页改版第二期"
              required
            />
          </div>
          <div className="field">
            <label htmlFor="new-owner">负责人</label>
            <input id="new-owner" value={owner} onChange={(event) => setOwner(event.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="new-primary">主指标</label>
            <select
              id="new-primary"
              value={primaryId}
              onChange={(event) => setPrimaryId(Number(event.target.value))}
            >
              {primaryOptions.map((metric) => (
                <option key={metric.id} value={metric.id}>
                  {metric.name}（{metric.kind === 'ratio' ? '比例' : '均值'}）
                </option>
              ))}
            </select>
          </div>
          <div className="field wide">
            <label>守卫指标（显著变差则结论降级）</label>
            <div className="list-check">
              {guardOptions.map((metric) => (
                <label key={metric.id}>
                  <input
                    type="checkbox"
                    checked={guardIds.includes(metric.id)}
                    onChange={(event) =>
                      setGuardIds((current) =>
                        event.target.checked
                          ? [...current, metric.id]
                          : current.filter((id) => id !== metric.id),
                      )
                    }
                  />
                  {metric.name}
                </label>
              ))}
            </div>
          </div>
          <div className="field wide">
            <label htmlFor="new-hypothesis">实验假设</label>
            <textarea
              id="new-hypothesis"
              value={hypothesis}
              onChange={(event) => setHypothesis(event.target.value)}
              placeholder="写清「改什么、期望哪个指标变、为什么」"
            />
          </div>
          <div className="field">
            <label htmlFor="new-control">对照组名称</label>
            <input id="new-control" value={controlName} onChange={(event) => setControlName(event.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="new-treat">实验组名称</label>
            <input id="new-treat" value={treatName} onChange={(event) => setTreatName(event.target.value)} />
          </div>
          <div className="field wide">
            <label htmlFor="new-notes">备注（口径 / 埋点注意事项）</label>
            <textarea id="new-notes" value={notes} onChange={(event) => setNotes(event.target.value)} />
          </div>
        </div>
        {error ? (
          <div className="annotation" role="alert">
            <span className="annotation-label">错误</span>
            {error}
          </div>
        ) : null}
        <div className="row">
          <button className="btn ink" type="submit" disabled={saving || !primaryOptions.length}>
            {saving ? '保存中…' : '保存实验'}
          </button>
          <button className="btn ghost" type="button" onClick={onCancel}>
            取消
          </button>
          {!primaryOptions.length ? <span className="hint">没有可用主指标，请先检查指标定义。</span> : null}
        </div>
      </form>
    </SheetPanel>
  );
};
