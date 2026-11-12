/** 登录页：记录本封面 + 三账号快捷填充。 */
import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { usePageTitle } from '../hooks/usePageTitle';
import { errorMessage } from '../utils/errorMessage';
import { ROLE_DUTY, ROLE_LABEL } from '../constants/roles';
import type { Role } from '../types/models';

const DEMO_ACCOUNTS: Array<{ email: string; role: Role }> = [
  { email: 'admin@abcheck.io', role: 'admin' },
  { email: 'analyst@abcheck.io', role: 'analyst' },
  { email: 'pm@abcheck.io', role: 'pm' },
];

export const LoginPage = () => {
  usePageTitle('登录');
  const login = useAuthStore((state) => state.login);
  const navigate = useNavigate();
  const [email, setEmail] = useState('analyst@abcheck.io');
  const [password, setPassword] = useState('Demo@2026');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(email.trim(), password);
      navigate('/experiments', { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="login-wrap">
      <section className="login-cover">
        <span className="kicker">QINGYOU MOBILITY · GROWTH LAB · 2026</span>
        <h1 className="login-title">
          abcheck
          <span className="zh">A/B 实验分流校验与显著性判定台</span>
        </h1>
        <div className="cover-rule" />
        <p style={{ maxWidth: '46ch', color: 'var(--ink-soft)' }}>
          每页一条实验流水：先查分流比例是否失衡（SRM），再比主指标与守卫指标，
          最后按固定规则给出 pass / warn / fail / unreadable——不再把 0.3pp 的差值当成「赢了」。
        </p>
        <div className="cover-meta">
          <div>委托方：青柚出行 · 增长分析组（9 人 · 每周 4 个线上实验）</div>
          <div>记录范围：4 个实验 / 8 个变体 / 5 个指标 / 3,800 条分桶曝光 / 3 个分析批次</div>
          <div>判定口径：SRM χ² 拟合优度 · 比例两比例 z（合并方差）· 均值 Welch t · BH FDR</div>
          <div>锁定规则：p(SRM) &lt; 0.001 → 结论不可读，指标差异一律不采信</div>
        </div>
        <div className="stamp red" style={{ alignSelf: 'flex-start', marginTop: 'auto' }}>
          LAB NOTEBOOK · 2026-11
        </div>
      </section>

      <section className="login-panel">
        <div className="login-card">
          <h2>登录记录本</h2>
          <p className="hint" style={{ marginBottom: 18 }}>
            使用演示账号进入；三个角色的可见范围与写权限不同。
          </p>
          <form className="stack" onSubmit={onSubmit}>
            <div className="field">
              <label htmlFor="email">邮箱</label>
              <input
                id="email"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="password">密码</label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </div>
            {error ? (
              <div className="annotation" role="alert">
                <span className="annotation-label">错误</span>
                {error}
              </div>
            ) : null}
            <button className="btn ink" type="submit" disabled={submitting}>
              {submitting ? '核对中…' : '进入记录本'}
            </button>
          </form>

          <div className="demo-accounts">
            <span className="stat-label">演示账号 · 密码统一 Demo@2026</span>
            {DEMO_ACCOUNTS.map((account) => (
              <button
                key={account.email}
                type="button"
                className="account-chip"
                onClick={() => {
                  setEmail(account.email);
                  setPassword('Demo@2026');
                }}
              >
                <strong>{ROLE_LABEL[account.role]}</strong>{' '}
                <span className="mono">{account.email}</span>
                <span className="hint" style={{ display: 'block' }}>
                  {ROLE_DUTY[account.role]}
                </span>
              </button>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
};
