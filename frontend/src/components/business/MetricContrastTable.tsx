/** 指标对比表：比例用 z 检验、均值用 Welch t，展示 lift / CI / p / MDE。 */
import type { MetricComparison } from '../../types/models';
import { METRIC_KIND_SHORT, METRIC_ROLE_LABEL } from '../../constants/enums';
import { fmtCi, fmtNum, fmtP, fmtPct, fmtPp, fmtSignedPct } from '../../utils/format';
import { RuledTable, type Column } from '../common/RuledTable';

interface MetricContrastTableProps {
  metrics: MetricComparison[];
  alpha?: number;
}

const testLabel = (test: string): string => (test === 'welch_t' ? 'Welch t' : '两比例 z');

export const MetricContrastTable = ({ metrics, alpha = 0.05 }: MetricContrastTableProps) => {
  const columns: Column<MetricComparison>[] = [
    {
      key: 'metric',
      label: '指标',
      render: (row) => (
        <span>
          <strong>{row.metric.name}</strong>
          <span className="hint" style={{ marginLeft: 8 }}>
            {METRIC_ROLE_LABEL[row.family]}
          </span>
        </span>
      ),
    },
    {
      key: 'kind',
      label: '口径',
      render: (row) => (
        <span className="hint">
          {METRIC_KIND_SHORT[row.kind]} · {testLabel(row.stat.test)}
        </span>
      ),
    },
    {
      key: 'control',
      label: '对照组',
      align: 'right',
      render: (row) =>
        row.kind === 'ratio' ? fmtPct(row.control_value) : fmtNum(row.control_value),
    },
    {
      key: 'treat',
      label: '实验组',
      align: 'right',
      render: (row) => (row.kind === 'ratio' ? fmtPct(row.treat_value) : fmtNum(row.treat_value)),
    },
    {
      key: 'diff',
      label: '差值',
      align: 'right',
      render: (row) => (row.kind === 'ratio' ? fmtPp(row.stat.diff) : fmtNum(row.stat.diff, 2)),
    },
    {
      key: 'lift',
      label: 'lift',
      align: 'right',
      render: (row) => (
        <span className={row.stat.lift !== null && row.stat.lift < 0 ? 'neg-text' : ''}>
          {fmtSignedPct(row.stat.lift)}
        </span>
      ),
    },
    {
      key: 'ci',
      label: 'lift 95% CI',
      align: 'right',
      render: (row) => <span className="hint">{fmtCi(row.stat.lift_ci95)}</span>,
    },
    {
      key: 'p',
      label: 'p 值',
      align: 'right',
      render: (row) => (
        <span className={row.stat.p_value < alpha ? 'sig-text' : ''}>{fmtP(row.stat.p_value)}</span>
      ),
    },
    {
      key: 'mde',
      label: 'MDE(80%)',
      align: 'right',
      render: (row) => fmtPct(row.stat.mde_required?.relative ?? null),
    },
    {
      key: 'verdict',
      label: '显著性',
      align: 'center',
      render: (row) =>
        row.stat.p_value < alpha ? (
          <span className="pill ok">p &lt; α</span>
        ) : (
          <span className="pill">未达显著</span>
        ),
    },
  ];

  return (
    <RuledTable
      columns={columns}
      rows={metrics}
      rowKey={(row) => row.metric.id}
      flagged={(row) => row.family === 'guard' && row.stat.p_value < alpha}
    />
  );
};
