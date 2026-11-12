import { api } from './client';
import type { DecisionKind, DecisionRecord } from '../types/models';

export const listDecisions = (experimentId?: number): Promise<DecisionRecord[]> =>
  api.get<DecisionRecord[]>(`/decisions${experimentId ? `?experiment_id=${experimentId}` : ''}`);

export const createDecision = (
  experimentId: number,
  payload: { decision: DecisionKind; rationale: string; guard_ack: boolean },
): Promise<DecisionRecord> => api.post<DecisionRecord>(`/experiments/${experimentId}/decisions`, payload);
