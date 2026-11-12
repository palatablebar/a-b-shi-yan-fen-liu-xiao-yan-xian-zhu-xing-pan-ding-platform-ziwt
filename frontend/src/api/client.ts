/** fetch 封装：统一鉴权头、错误体解析、401 回调、文件下载。 */
import type { ApiErrorPayload } from '../types/api';

const TOKEN_KEY = 'abcheck.token';

export class ApiError extends Error {
  status: number;
  code: string;
  detail?: unknown;

  constructor(message: string, status: number, code = 'http_error', detail?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

export const getToken = (): string | null => localStorage.getItem(TOKEN_KEY);
export const setToken = (token: string | null): void => {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
};

let unauthorizedHandler: (() => void) | null = null;
export const onUnauthorized = (handler: () => void): void => {
  unauthorizedHandler = handler;
};

const buildHeaders = (init?: HeadersInit, hasJsonBody = false): Headers => {
  const headers = new Headers(init);
  headers.set('Accept', 'application/json');
  if (hasJsonBody) headers.set('Content-Type', 'application/json');
  const token = getToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  return headers;
};

async function parseError(response: Response): Promise<ApiError> {
  let payload: ApiErrorPayload | null = null;
  try {
    payload = (await response.json()) as ApiErrorPayload;
  } catch {
    payload = null;
  }
  if (response.status === 401) unauthorizedHandler?.();
  return new ApiError(
    payload?.message ?? `请求失败（HTTP ${response.status}）`,
    response.status,
    payload?.code ?? 'http_error',
    payload?.detail,
  );
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const hasBody = init.body !== undefined;
  const response = await fetch(`/api${path}`, { ...init, headers: buildHeaders(init.headers, hasBody) });
  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body: body === undefined ? undefined : JSON.stringify(body) }),
  del: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
};

/** 触发浏览器下载（报告 MD/CSV）。 */
export const downloadFile = async (path: string, fallbackName: string): Promise<void> => {
  const token = getToken();
  const response = await fetch(`/api${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (!response.ok) throw await parseError(response);
  const blob = await response.blob();
  const disposition = response.headers.get('content-disposition') ?? '';
  const match = /filename="?([^"]+)"?/.exec(disposition);
  const filename = match?.[1] ?? fallbackName;
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
};
