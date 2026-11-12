/** 把后端错误体 / 网络错误统一成可展示的文案。 */
export const errorMessage = (error: unknown): string => {
  if (!error) return '未知错误';
  if (typeof error === 'string') return error;
  if (error instanceof Error) {
    const message = error.message || '请求失败';
    return message === 'Failed to fetch' ? '无法连接后端服务，请确认容器已启动' : message;
  }
  const record = error as Record<string, unknown>;
  if (typeof record.message === 'string') return record.message;
  return '请求失败，请稍后重试';
};
