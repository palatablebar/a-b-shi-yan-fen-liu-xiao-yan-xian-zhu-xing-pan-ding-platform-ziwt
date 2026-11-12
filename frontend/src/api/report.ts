import { api, downloadFile } from './client';
import type { ReportPreview } from '../types/api';

export const previewReport = (experimentId: number): Promise<ReportPreview> =>
  api.get<ReportPreview>(`/reports/experiments/${experimentId}/preview`);

export const downloadReport = (experimentId: number, format: 'md' | 'csv'): Promise<void> =>
  downloadFile(
    `/reports/experiments/${experimentId}.${format}`,
    `abcheck-experiment-${experimentId}-report.${format}`,
  );
