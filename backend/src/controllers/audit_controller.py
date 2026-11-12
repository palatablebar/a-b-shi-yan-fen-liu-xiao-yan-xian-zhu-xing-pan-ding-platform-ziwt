"""审计日志控制器。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.constants.limits import DEFAULT_AUDIT_LIMIT, MAX_AUDIT_LIMIT
from src.services.audit_service import AuditService


def list_audit_logs(db: Session, limit: int = DEFAULT_AUDIT_LIMIT) -> list[dict]:
    limit = max(1, min(limit, MAX_AUDIT_LIMIT))
    rows = AuditService(db).list_logs(limit)
    return [
        {
            "id": row.id,
            "actor_email": row.actor_email,
            "actor_role": row.actor_role,
            "action": row.action,
            "method": row.method,
            "path": row.path,
            "status_code": row.status_code,
            "detail": row.detail,
            "ip": row.ip,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
