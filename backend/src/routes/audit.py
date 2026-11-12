"""审计路由（admin/analyst 可读）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import audit_controller
from src.middlewares.rbac import require_permission
from src.models.user import User

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def list_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("audit:read")),
) -> list[dict]:
    return audit_controller.list_audit_logs(db, limit)
