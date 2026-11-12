"""RBAC 角色与能力矩阵。

前后端必须一致：users.role / constants/roles.py / frontend/src/constants/roles.ts / <RequireRole>。
"""
from __future__ import annotations

ROLE_ADMIN = "admin"      # 增长负责人：实验/指标/裁决规则
ROLE_ANALYST = "analyst"  # 数据分析师：建实验、跑分析、写结论
ROLE_PM = "pm"            # 产品经理：只读结论与报告

ALL_ROLES: tuple[str, ...] = (ROLE_ADMIN, ROLE_ANALYST, ROLE_PM)

PERMISSIONS: dict[str, tuple[str, ...]] = {
    "meta:read": ALL_ROLES,
    "experiments:read": ALL_ROLES,
    "experiments:write": (ROLE_ADMIN, ROLE_ANALYST),
    "experiments:delete": (ROLE_ADMIN,),
    "metrics:read": ALL_ROLES,
    "metrics:write": (ROLE_ADMIN,),
    "assignments:read": ALL_ROLES,
    "runs:read": ALL_ROLES,
    "runs:trigger": (ROLE_ADMIN, ROLE_ANALYST),
    "decisions:read": ALL_ROLES,
    "decisions:write": (ROLE_ADMIN,),
    "reports:export": ALL_ROLES,
    "audit:read": (ROLE_ADMIN, ROLE_ANALYST),
}

ROLE_LABELS: dict[str, str] = {
    ROLE_ADMIN: "增长负责人",
    ROLE_ANALYST: "数据分析师",
    ROLE_PM: "产品经理",
}


def role_can(role: str, action: str) -> bool:
    return role in PERMISSIONS.get(action, ())


def role_permissions(role: str) -> list[str]:
    return [action for action, roles in PERMISSIONS.items() if role in roles]
