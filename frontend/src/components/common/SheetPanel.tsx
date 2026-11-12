/** 记录本面板：标题行 + 手写编号 + 页脚注。所有页面共用。 */
import type { ReactNode } from 'react';

interface SheetPanelProps {
  title: string;
  index?: string;
  note?: string;
  actions?: ReactNode;
  children: ReactNode;
  dense?: boolean;
  className?: string;
}

export const SheetPanel = ({
  title,
  index,
  note,
  actions,
  children,
  dense = false,
  className = '',
}: SheetPanelProps) => (
  <section className={`sheet${dense ? ' dense' : ''}${className ? ` ${className}` : ''}`}>
    <header className="sheet-head">
      {index ? <span className="sheet-index">{index}</span> : null}
      <h3 className="sheet-title">{title}</h3>
      {actions ? <span style={{ marginLeft: 'auto' }}>{actions}</span> : null}
      {note ? <span className="sheet-note">{note}</span> : null}
    </header>
    <div className="sheet-body">{children}</div>
  </section>
);
