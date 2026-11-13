/** 枚举标签与视觉映射（后端副本：backend/src/constants/enums.py）。 */
import type {
  DecisionKind,
  ExperimentStatus,
  GuardState,
  MetricDirection,
  MetricKind,
  MetricRole,
  RunStatus,
  ShipState,
  SrmVerdict,
  Verdict,
} from '../types/models';

export const METRIC_KIND_LABEL: Record<MetricKind, string> = {
  ratio: '比例指标',
  mean: '均值指标',
};

export const METRIC_KIND_SHORT: Record<MetricKind, string> = {
  ratio: '比例',
  mean: '均值',
};

export const METRIC_ROLE_LABEL: Record<MetricRole, string> = {
  primary: '主指标',
  guard: '守卫指标',
  secondary: '辅助指标',
};

export const METRIC_DIRECTION_LABEL: Record<MetricDirection, string> = {
  increase_good: '越高越好',
  decrease_good: '越低越好',
};

export const EXPERIMENT_STATUS_LABEL: Record<ExperimentStatus, string> = {
  draft: '草稿',
  running: '进行中',
  analyzing: '待处置',
  decided: '已裁决',
  archived: '已归档',
};

export const RUN_STATUS_LABEL: Record<RunStatus, string> = {
  pending: '排队中',
  running: '计算中',
  succeeded: '已完成',
  failed: '失败',
};

export const VERDICT_LABEL: Record<Verdict, string> = {
  pass: '通过 pass',
  warn: '警告 warn',
  fail: '不通过 fail',
  unreadable: '不可读 unreadable',
};

export const VERDICT_SHORT: Record<Verdict, string> = {
  pass: 'PASS',
  warn: 'WARN',
  fail: 'FAIL',
  unreadable: 'UNREADABLE',
};

export const SRM_LABEL: Record<SrmVerdict, string> = {
  ok: '分流正常',
  detected: 'SRM 失衡',
  insufficient: '曝光不足',
};

export const GUARD_STATE_LABEL: Record<GuardState, string> = {
  ok: '正常',
  improved: '显著变好',
  regression: '显著变差',
  inconclusive: '无显著变化',
};

export const SHIP_STATE_LABEL: Record<ShipState, string> = {
  ship_eligible: '可上线',
  watch_only: '仅观察',
  blocked: '禁止上线',
};

export const SHIP_STATE_HINT: Record<ShipState, string> = {
  ship_eligible: '主指标经全方案 BH 校正后仍显著，且守卫无回归：本实验唯一可放量的赢家',
  watch_only: '主指标显著但存在分层异质/功效边界：只能继续观察或带风险评审',
  blocked: '守卫生效或全方案 BH 校正后失真：不能被当成赢家',
};

export const DECISION_LABEL: Record<DecisionKind, string> = {
  ship: '上线',
  kill: '下线',
  continue: '继续观察',
};

export const DECISION_OPTIONS: DecisionKind[] = ['ship', 'continue', 'kill'];

export const DECISION_HINT: Record<DecisionKind, string> = {
  ship: '主指标显著且守卫无回归时放量上线',
  continue: '分层异质或功效边界时延长观察',
  kill: '主指标不显著或守卫指标显著变差时下线',
};
