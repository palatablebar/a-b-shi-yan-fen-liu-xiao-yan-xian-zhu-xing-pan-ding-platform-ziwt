/** 角色常量（后端副本：backend/src/constants/roles.py，两处必须一致）。 */
import type { Role } from '../types/models';

export const ROLE_ADMIN: Role = 'admin';
export const ROLE_ANALYST: Role = 'analyst';
export const ROLE_PM: Role = 'pm';

export const ALL_ROLES: Role[] = [ROLE_ADMIN, ROLE_ANALYST, ROLE_PM];

export const ROLE_LABEL: Record<Role, string> = {
  admin: '增长负责人',
  analyst: '数据分析师',
  pm: '产品经理',
};

export const ROLE_DUTY: Record<Role, string> = {
  admin: '维护实验/指标口径与裁决规则，最终裁决上线',
  analyst: '建实验、跑分析、写分层结论',
  pm: '只读结论与报告，不触发分析、不落决策',
};

/** 能力矩阵（前端只做展示层禁用；真实 403 由后端 RBAC 返回）。 */
export const PERMISSIONS: Record<string, Role[]> = {
  'meta:read': ALL_ROLES,
  'experiments:read': ALL_ROLES,
  'experiments:write': [ROLE_ADMIN, ROLE_ANALYST],
  'experiments:delete': [ROLE_ADMIN],
  'metrics:write': [ROLE_ADMIN],
  'assignments:read': ALL_ROLES,
  'runs:read': ALL_ROLES,
  'runs:trigger': [ROLE_ADMIN, ROLE_ANALYST],
  'decisions:read': ALL_ROLES,
  'decisions:write': [ROLE_ADMIN],
  'reports:export': ALL_ROLES,
  'audit:read': [ROLE_ADMIN, ROLE_ANALYST],
};

export const can = (role: Role | undefined, action: string): boolean =>
  Boolean(role && (PERMISSIONS[action] ?? []).includes(role));
