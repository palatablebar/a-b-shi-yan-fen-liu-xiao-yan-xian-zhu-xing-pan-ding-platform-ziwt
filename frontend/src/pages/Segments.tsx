/** 分层分析：城市 × 客群下钻 + 分层内 BH 校正 + 全量判定说明。 */
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useAsync } from '../hooks/useAsync';
import { usePageTitle } from '../hooks/usePageTitle';
import { getSegments, listExperiments } from '../api/experiment';
import { fmtInt, fmtPct } from '../utils/format';
import { SRM_LABEL, VERDICT_LABEL } from '../constants/enums';
import { srmTone } from '../utils/display';
import { SheetPanel } from '../components/common/SheetPanel';
import { BhTable } from '../components/business/BhTable';
import { LiftCiPlot, type LiftCiRow } from '../components/business/LiftCiPlot';
import { Annotation } from '../components/common/Annotation';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorNote } from '../components/common/ErrorNote';
import { StatusPill } from '../components/common/StatusPill';
import { VerdictStamp } from '../components/common/VerdictStamp';

export const SegmentsPage = () => {
  const params = useParams();
  const [search] = useSearchParams();
  const experimentId = Number(params.experimentId ?? search.get('experimentId') ?? 0);
  const experiments = useAsync(listExperiments, []);
  const view = useAsync(
    () => (experimentId ? getSegments(experimentId) : Promise.resolve(null)),
    [experimentId],
  );
  usePageTitle(view.data?.experiment ? `${view.data.experiment.code} 分层分析` : '分层校正');

  if (!experimentId) {
    return (
      <div>
        <div className="page-head">
          <div>
            <div className="kicker">STRATA / 03</div>
            <h1>分层下钻与多重比较校正</h1>
            <p className="sub">选择实验进入城市 × 客群分层：看哪些分层是「挑出来的显著」。</p>
          </div>
        </div>
        <SheetPanel title="选择实验" index="A" note="按最近批次结论排序">
          {experiments.loading ? (
            <p className="loading-note">正在读取实验…</p>
          ) : experiments.error ? (
            <ErrorNote message={experiments.error} onRetry={experiments.reload} />
          ) : (experiments.data ?? []).length === 0 ? (
            <EmptyState title="还没有实验">先在实验索引里新建实验并导入分桶数据。</EmptyState>
          ) : (
            <div style={{ display: 'grid', gap: 8 }}>
              {(experiments.data ?? []).map((experiment) => (
                <Link
                  key={experiment.id}
                  className="run-item"
                  to={`/segments?experimentId=${experiment.id}`}
                  style={{ display: 'block', textDecoration: 'none' }}
                >
                  <div className="row-between">
                    <span>
                      <strong>{experiment.name}</strong>
                      <span className="hint mono" style={{ marginLeft: 8 }}>
                        {experiment.code}
                      </span>
                    </span>
                    <VerdictStamp verdict={experiment.latest_verdict} animate={false} />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </SheetPanel>
      </div>
    );
  }

  if (view.loading && !view.data) return <p className="loading-note">正在读取分层结果…</p>;
  if (view.error) return <ErrorNote message={view.error} onRetry={view.reload} />;
  const data = view.data;
  if (!data) {
    return (
      <EmptyState title="该实验还没有可用的分析批次">
        先到实验详情触发一次分析；分层结果会随批次一起落库。
      </EmptyState>
    );
  }

  const { strata, experiment, run, primary } = data;
  const kind = primary?.kind ?? 'ratio';
  const rows: LiftCiRow[] = strata.cells
    .filter((cell) => cell.lift !== null)
    .map((cell) => ({
      label: `${cell.segment_city}·${cell.segment_tenure}`,
      lift: cell.lift,
      ci: cell.stat?.lift_ci95 ?? null,
      significant: cell.significant_bh,
      muted: !cell.significant_raw,
    }));

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="kicker">STRATA / 03 · {experiment.code.toUpperCase()}</div>
          <h1>分层下钻与多重比较校正</h1>
          <p className="sub">
            <Link className="inline-link" to={`/experiments/${experiment.id}`}>
              ← 返回实验详情
            </Link>
            {' · '}
            {primary?.metric.name ?? '主指标'} · {kind === 'ratio' ? '比例口径' : '均值口径'} · 批次{' '}
            {run.run_code}
          </p>
        </div>
        <div className="head-aside">
          <VerdictStamp verdict={run.verdict ?? null} animate={false} />
          <div style={{ marginTop: 6 }}>
            <StatusPill tone={srmTone(run.srm?.verdict)}>{SRM_LABEL[run.srm?.verdict ?? 'ok']}</StatusPill>
          </div>
        </div>
      </div>

      <div className="split split-3" style={{ marginBottom: 16 }}>
        <SheetPanel title="分层单元格" index="A" note="城市 × 新老客">
          <dl className="kv">
            <dt>单元格总数</dt>
            <dd className="mono">{fmtInt(strata.summary.cells_total)}</dd>
            <dt>可检验</dt>
            <dd className="mono">{fmtInt(strata.summary.cells_tested)}</dd>
            <dt>样本不足</dt>
            <dd className="mono">{fmtInt(strata.summary.insufficient_cells)}</dd>
            <dt>BH 校正</dt>
            <dd className="mono">m={strata.family.m} · α={strata.family.alpha}</dd>
          </dl>
        </SheetPanel>
        <SheetPanel title="原始显著" index="B" note="p < α">
          <div className="big-num" style={{ color: 'var(--red)' }}>
            {fmtInt(strata.summary.raw_significant)}
          </div>
          <p className="hint">未经多重比较校正时会「看起来显著」的分层数。</p>
        </SheetPanel>
        <SheetPanel title="校正后不显著" index="C" note="p < α 但 q ≥ α">
          <div className="big-num" style={{ color: 'var(--fail)' }}>
            {fmtInt(strata.summary.flagged_non_significant)}
          </div>
          <p className="hint">BH 校正后不再显著：这是结论判 warn 的主要依据。</p>
        </SheetPanel>
      </div>

      <SheetPanel
        title="分层效应量森林图"
        index="D"
        note={`${primary?.metric.name ?? '主指标'} · lift 与 95% CI`}
      >
        <LiftCiPlot rows={rows} title="分层 lift 与 95% 置信区间" />
        <Annotation>
          绿色 = BH 校正后仍显著；灰色虚线跨越 0 的分层不显著。
          若出现「多个分层原始显著、校正后全部不显著」，说明效应集中在被反复挑中的少数分层，不能据此放量。
        </Annotation>
      </SheetPanel>

      <div style={{ marginTop: 16 }}>
        <SheetPanel
          title="分层 BH 校正明细"
          index="E"
          note="q 值 = BH 校正后 p；红色行 = 校正后不显著"
        >
          <BhTable strata={strata} kind={kind} />
        </SheetPanel>
      </div>

      <p className="hint" style={{ marginTop: 12 }}>
        判定说明：本页只展示分层结果，整体结论由批次页的固定规则给出（{VERDICT_LABEL[run.verdict ?? 'warn']}）。
        可检验下限为每臂 25 人；低于该值的分层标记「不可检验」，不参与 BH。
        {primary ? ` 主指标基线 ${fmtPct(primary.control_value ?? null)}。` : ''}
      </p>
    </div>
  );
};
