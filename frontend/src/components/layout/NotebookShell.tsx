/** 记录本外壳：品牌区 / 索引标签 / 题头 / 页脚统计注。 */
import type { ReactNode } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';
import { ROLE_LABEL } from '../../constants/roles';
import { useAsync } from '../../hooks/useAsync';
import { fetchOverview } from '../../api/meta';
import { fmtInt } from '../../utils/format';

const NAV = [
  { to: '/experiments', label: '实验索引', idx: '01', action: 'experiments:read', hint: 'INDEX' },
  { to: '/runs', label: '分析批次', idx: '02', action: 'runs:read', hint: 'RUNS' },
  { to: '/segments', label: '分层校正', idx: '03', action: 'experiments:read', hint: 'STRATA' },
  { to: '/decisions', label: '报告与决策', idx: '04', action: 'decisions:read', hint: 'DECIDE' },
];

const pageTitleFor = (path: string): string => {
  if (/^\/experiments\/\d+\/segments$/.test(path)) return '分层下钻与多重比较校正';
  if (/^\/experiments\/\d+$/.test(path)) return '实验详情与显著性判定';
  if (path.startsWith('/experiments')) return '实验索引与分流台账';
  if (path.startsWith('/runs')) return '分析批次与显著性判定';
  if (path.startsWith('/segments')) return '分层下钻与多重比较校正';
  if (path.startsWith('/decisions')) return '报告导出与决策记录';
  return '实验索引与分流台账';
};

export const NotebookShell = ({ children }: { children: ReactNode }) => {
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const navigate = useNavigate();
  const { data: overview } = useAsync(fetchOverview, [], Boolean(user));
  const title = pageTitleFor(window.location.pathname);

  return (
    <div className="shell">
      <div className="brand">
        <span className="brand-mark">ab</span>
        <div>
          <div className="brand-name">abcheck</div>
          <span className="brand-tag">青柚出行 · 增长分析组</span>
        </div>
      </div>

      <header className="topbar">
        <span className="topbar-kicker">LAB NOTEBOOK / 记录本</span>
        <span className="topbar-title">{title}</span>
        <span className="topbar-spacer" />
        <div className="topbar-actor">
          <span className="pill neutral" title="当前角色">
            {user ? ROLE_LABEL[user.role] : '未登录'}
          </span>
          <span className="mono" style={{ fontSize: 10, color: 'var(--ink-faint)' }}>
            {user?.email ?? ''}
          </span>
          <button
            className="btn ghost small"
            onClick={() => {
              logout();
              navigate('/login', { replace: true });
            }}
          >
            退出
          </button>
        </div>
      </header>

      <nav className="rail" aria-label="记录本索引">
        <div className="rail-label">目录 / CONTENTS</div>
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => `rail-item${isActive ? ' active' : ''}`}
          >
            <span className="idx">{item.idx}</span>
            <span>{item.label}</span>
            <span className="rail-hint">{item.hint}</span>
          </NavLink>
        ))}
        <div className="rail-foot">
          <div>
            实验 <span className="mono">{fmtInt(overview?.experiments ?? null)}</span> · 批次{' '}
            <span className="mono">{fmtInt(overview?.runs ?? null)}</span>
          </div>
          <div>
            分桶 <span className="mono">{fmtInt(overview?.assignments ?? null)}</span> · SRM{' '}
            <span className="mono">{fmtInt(overview?.srm_alerts ?? null)}</span>
          </div>
          <div>
            worker 心跳{' '}
            <span className="mono">
              {overview?.worker_heartbeat_age !== null && overview?.worker_heartbeat_age !== undefined
                ? `${overview.worker_heartbeat_age}s`
                : '—'}
            </span>
          </div>
        </div>
      </nav>

      <main className="main">{children}</main>

      <footer className="foot">
        <span>注：分流校验按曝光次数口径；指标检验按用户级样本；多重比较用 BH FDR 校正。</span>
        <span>记录人 {user?.email ?? '—'}</span>
        <span>
          分桶 {fmtInt(overview?.assignments ?? null)} 条 · 待裁决{' '}
          {fmtInt(overview?.pending_decisions ?? null)} 项
        </span>
        <span>abcheck v1.0 · 2026-11</span>
      </footer>
    </div>
  );
};
