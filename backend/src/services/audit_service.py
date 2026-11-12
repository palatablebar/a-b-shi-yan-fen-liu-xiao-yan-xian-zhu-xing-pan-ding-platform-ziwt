"""审计留痕：写操作统一落到 audit_logs。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.models.audit_log import AuditLog


class AuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        actor_email: str,
        actor_role: str,
        action: str,
        method: str,
        path: str,
        status_code: int,
        detail: dict | None = None,
        ip: str = "",
    ) -> AuditLog:
        log = AuditLog(
            actor_email=actor_email,
            actor_role=actor_role,
            action=action,
            method=method,
            path=path,
            status_code=status_code,
            detail=detail or {},
            ip=ip,
        )
        self.db.add(log)
        self.db.commit()
        return log

    def list_logs(self, limit: int = 50) -> list[AuditLog]:
        return (
            self.db.query(AuditLog)
            .order_by(AuditLog.id.desc())
            .limit(limit)
            .all()
        )
