import { api } from './client';
import type { ExperimentDetail, ExperimentSummary, SegmentView } from '../types/models';

export const listExperiments = (): Promise<ExperimentSummary[]> =>
  api.get<ExperimentSummary[]>('/experiments');

export const getExperiment = (id: number): Promise<ExperimentDetail> =>
  api.get<ExperimentDetail>(`/experiments/${id}`);

export const getSegments = (id: number): Promise<SegmentView> =>
  api.get<SegmentView>(`/experiments/${id}/segments`);

export interface CreateExperimentPayload {
  code: string;
  name: string;
  hypothesis: string;
  description: string;
  owner_name: string;
  primary_metric_id: number;
  guard_metric_ids: number[];
  secondary_metric_ids: number[];
  variants: Array<{
    code: string;
    name: string;
    traffic_allocation: number;
    is_control: boolean;
    description: string;
  }>;
  notes: string;
}

export const createExperiment = (payload: CreateExperimentPayload): Promise<ExperimentSummary> =>
  api.post<ExperimentSummary>('/experiments', payload);

export const updateExperiment = (
  id: number,
  payload: Record<string, unknown>,
): Promise<ExperimentDetail> => api.patch<ExperimentDetail>(`/experiments/${id}`, payload);
