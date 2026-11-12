/** 状态胶囊：实验状态 / 批次状态 / SRM / 守卫指标共用。 */
import type { ReactNode } from 'react';
import type { Tone } from '../../utils/display';

interface StatusPillProps {
  tone?: Tone;
  children: ReactNode;
  dot?: boolean;
}

export const StatusPill = ({ tone = 'neutral', children, dot = true }: StatusPillProps) => (
  <span className={`pill ${tone}`}>
    {dot ? <i className="dot" /> : null}
    {children}
  </span>
);
