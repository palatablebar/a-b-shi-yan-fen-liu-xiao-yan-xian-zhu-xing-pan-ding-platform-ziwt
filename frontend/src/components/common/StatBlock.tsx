/** 关键数字块：label + 大号等宽数字 + 脚注。 */
import type { ReactNode } from 'react';

interface StatBlockProps {
  label: string;
  value: ReactNode;
  foot?: ReactNode;
  tone?: 'default' | 'red';
}

export const StatBlock = ({ label, value, foot, tone = 'default' }: StatBlockProps) => (
  <div className={`stat-block${tone === 'red' ? ' red' : ''}`}>
    <span className="stat-label">{label}</span>
    <div className="big-num">{value}</div>
    {foot ? <p className="hint">{foot}</p> : null}
  </div>
);
