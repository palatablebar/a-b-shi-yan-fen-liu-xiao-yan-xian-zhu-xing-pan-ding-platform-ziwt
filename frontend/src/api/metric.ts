import { api } from './client';
import type { Metric } from '../types/models';

export const listMetrics = (): Promise<Metric[]> => api.get<Metric[]>('/metrics');

export const updateMetric = (id: number, payload: Record<string, unknown>): Promise<Metric> =>
  api.patch<Metric>(`/metrics/${id}`, payload);
