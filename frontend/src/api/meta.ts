import { api } from './client';
import type { AuditLog, Overview } from '../types/models';
import type { HealthResponse } from '../types/api';

export const fetchOverview = (): Promise<Overview> => api.get<Overview>('/meta/overview');

export const fetchConfig = (): Promise<Record<string, unknown>> =>
  api.get<Record<string, unknown>>('/meta/config');

export const fetchAuditLogs = (limit = 20): Promise<AuditLog[]> =>
  api.get<AuditLog[]>(`/audit?limit=${limit}`);

export const fetchHealth = (): Promise<HealthResponse> => api.get<HealthResponse>('/health');
