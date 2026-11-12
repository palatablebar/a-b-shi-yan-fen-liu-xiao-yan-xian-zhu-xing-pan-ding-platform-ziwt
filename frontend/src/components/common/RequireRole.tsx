/** 前端权限门：只控制展示；真正 403 由后端 RBAC 返回。 */
import type { ReactNode } from 'react';
import { useAuthStore } from '../../stores/authStore';
import { can } from '../../constants/roles';

interface RequireRoleProps {
  action: string;
  children: ReactNode;
  fallback?: ReactNode;
}

export const RequireRole = ({ action, children, fallback = null }: RequireRoleProps) => {
  const role = useAuthStore((state) => state.user?.role);
  return <>{can(role, action) ? children : fallback}</>;
};
