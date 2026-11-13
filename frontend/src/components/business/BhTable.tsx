/** 分层多重比较表：显示原始 p 与 BH 校正后 q，突出「校正后不显著」的分层。 */
import type { StrataResult } from '../../types/models';
import { fmtNum, fmtP, fmtPct, fmtQ, fmtSignedPct } from '../../utils/format';
import { RuledTable, type Column } from '../common/RuledTable';
import type { MetricKind } from '../../types/models';

interface BhTableProps {
  strata: StrataResult;
  kind: MetricKind;
  showFullBh?: boolean;
}

export const BhTable = ({ strata, kind, showFullBh = false }: BhTableProps) => {
  const columns: Column<StrataResult['cells'][number]>[] = [
    {
      key: 'cell',
      label: '分层（城市 × 客群）',
      render: (row) => (
        <span>
          {row.segment_city} · {row.segment_tenure}
        </span>
      ),
    },
    {
      key: 'n',
      label: '对照 n / 实验 n',
      align: 'right',
      render: (row) => (
        <span className="mono">
          {row.control_n} / {row.treat_n}
        </span>
      ),
    },
    {
      key: 'control',
      label: '对照组',
      align: 'right',
      render: (row) =>
        row.control_value === null
          ? '—'
          : kind === 'ratio'
            ? fmtPct(row.control_value)
            : fmtNum(row.control_value),
    },
    {
      key: 'treat',
      label: '实验组',
      align: 'right',
      render: (row) =>
        row.treat_value === null
          ? '—'
          : kind === 'ratio'
            ? fmtPct(row.treat_value)
            : fmtNum(row.treat_value),
    },
    {
      key: 'lift',
      label: 'lift',
      align: 'right',
      render: (row) => fmtSignedPct(row.lift),
    },
    {
      key: 'p',
      label: 'p 值',
      align: 'right',
      render: (row) => <span className={row.significant_raw ? 'sig-text' : ''}>{fmtP(row.p_value)}</span>,
    },
    {
      key: 'q',
      label: '分层内 q (BH)',
      align: 'right',
      render: (row) => <span className={row.significant_bh ? 'sig-text' : ''}>{fmtQ(row.q_value)}</span>,
    },
    ...(showFullBh
      ? [
          {
            key: 'q_full',
            label: '全方案 q (BH)',
            align: 'right' as const,
            render: (row: StrataResult['cells'][number]) => (
              <span className={row.full_bh_reject ? 'sig-text' : ''}>
                {fmtQ(row.full_bh_q_value ?? null)}
              </span>
            ),
          },
        ]
      : []),
    {
      key: 'verdict',
      label: '判定',
      align: 'center',
      render: (row) => {
        if (row.p_value === null) return <span className="pill">不可检验</span>;
        if (row.significant_bh) return <span className="pill ok">BH 后显著</span>;
        if (row.significant_raw) return <span className="pill warn">校正后不显著</span>;
        return <span className="pill">不显著</span>;
      },
    },
  ];

  return (
    <RuledTable
      columns={columns}
      rows={strata.cells}
      rowKey={(row) => `${row.segment_city}-${row.segment_tenure}`}
      flagged={(row) => Boolean(row.significant_raw && !row.significant_bh)}
    />
  );
};
