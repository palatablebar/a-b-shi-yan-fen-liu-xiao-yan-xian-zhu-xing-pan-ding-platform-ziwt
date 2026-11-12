/** 空状态：告诉用户下一步该做什么，而不是只写「暂无数据」。 */
import type { ReactNode } from 'react';

interface EmptyStateProps {
  title: string;
  children: ReactNode;
  action?: ReactNode;
}

export const EmptyState = ({ title, children, action }: EmptyStateProps) => (
  <div className="empty">
    <h4>{title}</h4>
    <p>{children}</p>
    {action ? <div style={{ marginTop: 12 }}>{action}</div> : null}
  </div>
);
