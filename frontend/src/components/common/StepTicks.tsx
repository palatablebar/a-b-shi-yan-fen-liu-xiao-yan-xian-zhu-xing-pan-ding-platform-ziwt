/** 实验流程刻度：导入 → 分流校验 → 指标对比 → 分层 → 结论 → 决策。 */
const STEPS = ['分桶导入', '分流校验', '指标对比', '分层校正', '结论判定', '决策记录'];

interface StepTicksProps {
  current: number;
  broken?: boolean;
}

export const StepTicks = ({ current, broken = false }: StepTicksProps) => (
  <ol className="step-ticks">
    {STEPS.map((label, index) => {
      const done = index < current;
      const active = index === current;
      return (
        <li
          key={label}
          className={`tick${done ? ' done' : ''}${active ? ' active' : ''}${
            broken && index === 1 ? ' broken' : ''
          }`}
        >
          <span className="tick-no">{String(index + 1).padStart(2, '0')}</span>
          <span className="tick-label">{label}</span>
        </li>
      );
    })}
  </ol>
);
