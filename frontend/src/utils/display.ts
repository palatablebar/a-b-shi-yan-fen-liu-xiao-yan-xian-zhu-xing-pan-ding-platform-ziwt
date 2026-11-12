/** 判定/状态的视觉映射（颜色 token 仅在此处集中引用）。 */
import type {
  ExperimentStatus,
  GuardState,
  RunStatus,
  SrmVerdict,
  Verdict,
} from '../types/models';

export type Tone = 'ok' | 'warn' | 'fail' | 'unreadable' | 'neutral' | 'red';

export const verdictTone = (verdict: Verdict | null | undefined): Tone => {
  if (!verdict) return 'neutral';
  return verdict;
};

export const statusTone = (status: ExperimentStatus): Tone => {
  if (status === 'decided') return 'ok';
  if (status === 'analyzing') return 'unreadable';
  if (status === 'running') return 'warn';
  return 'neutral';
};

export const runTone = (status: RunStatus): Tone => {
  if (status === 'succeeded') return 'ok';
  if (status === 'failed') return 'fail';
  if (status === 'running') return 'warn';
  return 'neutral';
};

export const srmTone = (verdict: SrmVerdict | null | undefined): Tone => {
  if (!verdict) return 'neutral';
  if (verdict === 'detected') return 'fail';
  if (verdict === 'insufficient') return 'unreadable';
  return 'ok';
};

export const guardTone = (state: GuardState): Tone => {
  if (state === 'regression') return 'fail';
  if (state === 'improved') return 'ok';
  return 'neutral';
};

export const directionText = (lift: number | null | undefined): string => {
  if (lift === null || lift === undefined) return '—';
  if (lift > 0) return '高于对照';
  if (lift < 0) return '低于对照';
  return '持平';
};
