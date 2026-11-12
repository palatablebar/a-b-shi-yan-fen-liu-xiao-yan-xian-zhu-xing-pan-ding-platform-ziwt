/** 与后端 schemas 对齐的领域模型（只做展示，不做任何统计计算）。 */

export type Role = 'admin' | 'analyst' | 'pm';

export type MetricKind = 'ratio' | 'mean';
export type MetricRole = 'primary' | 'guard' | 'secondary';
export type MetricDirection = 'increase_good' | 'decrease_good';
export type ExperimentStatus = 'draft' | 'running' | 'analyzing' | 'decided' | 'archived';
export type RunStatus = 'pending' | 'running' | 'succeeded' | 'failed';
export type Verdict = 'pass' | 'warn' | 'fail' | 'unreadable';
export type SrmVerdict = 'ok' | 'detected' | 'insufficient';
export type DecisionKind = 'ship' | 'kill' | 'continue';
export type GuardState = 'ok' | 'improved' | 'regression' | 'inconclusive';

export interface User {
  id: number;
  email: string;
  display_name: string;
  role: Role;
  role_label: string;
  permissions: string[];
}

export interface Metric {
  id: number;
  code: string;
  name: string;
  kind: MetricKind;
  role: MetricRole;
  direction: MetricDirection;
  unit: string;
  definition: string;
}

export interface Variant {
  id: number;
  code: string;
  name: string;
  traffic_allocation: number;
  is_control: boolean;
  description: string;
  users: number;
  exposures: number;
}

export interface SrmResult {
  verdict: SrmVerdict;
  total: number;
  observed: number[] | null;
  expected: number[] | null;
  observed_share: number[] | null;
  expected_share: number[] | null;
  chi2: number | null;
  df: number | null;
  p_value: number | null;
  threshold: number;
  reason: string;
  unit?: string;
  variant_codes?: string[];
  variant_names?: string[];
  min_exposures?: number;
}

export interface MdeRequired {
  alpha: number;
  power: number;
  absolute: number;
  relative: number | null;
}

export interface MetricStat {
  test: 'two_proportion_z' | 'welch_t';
  control_n: number;
  treat_n: number;
  control_rate?: number;
  treat_rate?: number;
  pooled_rate?: number;
  control_mean?: number;
  treat_mean?: number;
  control_sd?: number;
  treat_sd?: number;
  diff: number;
  z?: number;
  t?: number;
  df?: number;
  p_value: number;
  lift: number | null;
  lift_ci95: [number, number] | null;
  mde_required: MdeRequired | null;
}

export interface MetricComparison {
  metric: Metric;
  family: 'primary' | 'guard' | 'secondary';
  kind: MetricKind;
  direction: MetricDirection;
  point_label: string;
  control_value: number | null;
  treat_value: number | null;
  stat: MetricStat;
}

export interface StrataCell {
  segment_city: string;
  segment_tenure: string;
  control_n: number;
  treat_n: number;
  testable: boolean;
  control_value: number | null;
  treat_value: number | null;
  diff: number | null;
  lift: number | null;
  p_value: number | null;
  q_value: number | null;
  significant_raw: boolean;
  significant_bh: boolean;
  note: string;
  stat?: MetricStat;
}

export interface FamilyResult {
  method: string;
  alpha: number;
  m: number;
  min_q: number | null;
  rejected: number;
}

export interface StrataResult {
  dimensions: string[];
  alpha: number;
  cells: StrataCell[];
  family: FamilyResult;
  summary: {
    cells_total: number;
    cells_tested: number;
    insufficient_cells: number;
    raw_significant: number;
    bh_significant: number;
    flagged_non_significant: number;
  };
}

export interface GuardCheck {
  code: string;
  name: string;
  direction: MetricDirection;
  diff: number;
  lift: number | null;
  p_value: number;
  q_value: number | null;
  reject: boolean;
  bad_direction: boolean;
  state: GuardState;
  note: string;
}

export interface GuardResult {
  checks: GuardCheck[];
  regression: boolean;
  family: FamilyResult;
}

export interface ComparisonRow {
  family: 'primary' | 'guard' | 'secondary' | 'strata';
  label: string;
  metric_code: string;
  p_value: number;
  q_value: number | null;
  rank: number | null;
  reject: boolean;
}

export interface ExperimentSummary {
  id: number;
  code: string;
  name: string;
  status: ExperimentStatus;
  owner_name: string;
  primary_metric_name: string | null;
  start_date: string | null;
  end_date: string | null;
  variants: number;
  assignments: number;
  latest_verdict: Verdict | null;
  latest_srm: SrmVerdict | null;
  latest_run_at: string | null;
}

export interface RunSummary {
  id: number;
  experiment_id: number;
  experiment_code: string | null;
  experiment_name: string | null;
  run_code: string;
  status: RunStatus;
  verdict: Verdict | null;
  locked: boolean;
  triggered_by: string;
  srm_verdict: SrmVerdict | null;
  srm_p_value: number | null;
  primary_lift: number | null;
  primary_p_value: number | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  error: string | null;
}

export interface RunDetail {
  id: number;
  experiment_id: number;
  run_code: string;
  status: RunStatus;
  verdict: Verdict | null;
  locked: boolean;
  triggered_by: string;
  params: Record<string, unknown> | null;
  srm: SrmResult | null;
  metrics: MetricComparison[] | null;
  strata: StrataResult | null;
  comparisons: ComparisonRow[] | null;
  guard: GuardResult | null;
  verdict_reasons: string[] | null;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  experiment: {
    id: number;
    code: string;
    name: string;
    status: ExperimentStatus;
    primary_metric: Pick<Metric, 'id' | 'code' | 'name' | 'kind' | 'unit'> | null;
  } | null;
}

export interface DecisionRecord {
  id: number;
  experiment_id: number;
  experiment_code: string | null;
  experiment_name: string | null;
  run_id: number;
  run_code: string | null;
  verdict: Verdict | null;
  decision: DecisionKind;
  rationale: string;
  reviewer: string;
  guard_ack: boolean;
  created_at: string;
}

export interface ExperimentDetail {
  id: number;
  code: string;
  name: string;
  hypothesis: string;
  description: string;
  owner_name: string;
  status: ExperimentStatus;
  alpha: number;
  srm_threshold: number;
  min_sample_per_arm: number;
  start_date: string | null;
  end_date: string | null;
  notes: string;
  created_by: string;
  updated_at: string;
  primary_metric: Metric | null;
  guard_metrics: Metric[];
  variants: Variant[];
  assignment_total: number;
  srm_snapshot: (SrmResult & { variants?: Array<Record<string, unknown>> }) | null;
  latest_run: {
    id: number;
    run_code: string;
    status: RunStatus;
    verdict: Verdict | null;
    locked: boolean;
    srm: SrmResult | null;
    primary_lift: number | null;
    primary_p_value: number | null;
    verdict_reasons: string[] | null;
    created_at: string | null;
    finished_at: string | null;
  } | null;
  decision: {
    id: number;
    decision: DecisionKind;
    rationale: string;
    reviewer: string;
    guard_ack: boolean;
    created_at: string;
  } | null;
}

export interface Overview {
  experiments: number;
  running: number;
  analyzing: number;
  decided: number;
  runs: number;
  assignments: number;
  metrics: number;
  pending_decisions: number;
  worker_heartbeat_age: number | null;
  srm_alerts: number;
}

export interface SegmentView {
  experiment: {
    id: number;
    code: string;
    name: string;
    status: ExperimentStatus;
    primary_metric: Metric | null;
  };
  run: {
    id: number;
    run_code: string;
    verdict: Verdict | null;
    created_at: string | null;
    srm: SrmResult | null;
  };
  strata: StrataResult;
  primary: MetricComparison | null;
}

export interface AuditLog {
  id: number;
  actor_email: string;
  actor_role: string;
  action: string;
  method: string;
  path: string;
  status_code: number;
  detail: Record<string, unknown> | null;
  ip: string;
  created_at: string | null;
}
