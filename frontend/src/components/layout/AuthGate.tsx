/** 登录门：无 token 直接回登录页；有 token 但用户信息未加载完成时显示核对中。 */
import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { getToken } from '../../api/client';
import { useAuthStore } from '../../stores/authStore';

export const AuthGate = ({ children }: { children: ReactNode }) => {
  const user = useAuthStore((state) => state.user);
  if (!getToken()) return <Navigate to="/login" replace />;
  if (!user) {
    return (
      <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }}>
        <p className="loading-note">正在核对记录本…</p>
      </div>
    );
  }
  return <>{children}</>;
};
