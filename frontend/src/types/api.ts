/** API 传输层：错误体、登录响应、上传/导出辅助类型。 */
import type { User } from './models';

export interface ApiErrorPayload {
  code: string;
  message: string;
  detail?: unknown;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface ReportPreview {
  markdown: string;
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  database: string;
  redis: string;
}
