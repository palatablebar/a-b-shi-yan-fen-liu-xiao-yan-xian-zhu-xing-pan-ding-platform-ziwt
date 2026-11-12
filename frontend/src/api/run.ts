import { api } from './client';
import type { RunDetail, RunSummary } from '../types/models';

export const triggerRun = (experimentId: number): Promise<RunSummary> =>
  api.post<RunSummary>(`/experiments/${experimentId}/runs`);

export const listRuns = (experimentId?: number): Promise<RunSummary[]> =>
  api.get<RunSummary[]>(`/runs${experimentId ? `?experiment_id=${experimentId}` : ''}`);

export const getRun = (runId: number): Promise<RunDetail> => api.get<RunDetail>(`/runs/${runId}`);
