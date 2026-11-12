/** 红色批注：实验记录本里的旁批，用于风险/口径说明。 */
import type { ReactNode } from 'react';

export const Annotation = ({ children }: { children: ReactNode }) => (
  <div className="annotation">
    <span className="annotation-label">批注</span>
    {children}
  </div>
);
