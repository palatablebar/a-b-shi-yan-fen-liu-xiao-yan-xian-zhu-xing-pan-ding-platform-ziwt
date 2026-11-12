/** 结论印章：pass/warn/fail/unreadable，落纸动画只在首次出现时播放。 */
import type { Verdict } from '../../types/models';
import { VERDICT_LABEL, VERDICT_SHORT } from '../../constants/enums';
import { verdictTone } from '../../utils/display';

interface VerdictStampProps {
  verdict: Verdict | null | undefined;
  large?: boolean;
  animate?: boolean;
}

export const VerdictStamp = ({ verdict, large = false, animate = true }: VerdictStampProps) => {
  if (!verdict) return <span className="stamp neutral">待判定</span>;
  const tone = verdictTone(verdict);
  return (
    <span
      className={`stamp ${tone}${large ? ' lg' : ''}${animate ? ' animate' : ''}`}
      title={VERDICT_LABEL[verdict]}
    >
      {VERDICT_SHORT[verdict]}
    </span>
  );
};
