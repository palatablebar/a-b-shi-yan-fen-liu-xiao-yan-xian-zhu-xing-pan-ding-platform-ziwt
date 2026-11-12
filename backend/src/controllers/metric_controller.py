"""指标控制器。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.models.user import User
from src.schemas.metric import MetricOut, MetricUpdate
from src.services.audit_service import AuditService
from src.services.metric_service import MetricService


def list_metrics(db: Session) -> list[MetricOut]:
    return MetricService(db).list_metrics()


def update_metric(
    metric_id: int, payload: MetricUpdate, request: Request, db: Session, user: User
) -> MetricOut:
    result = MetricService(db).update(metric_id, payload)
    AuditService(db).record(
        actor_email=user.email,
        actor_role=user.role,
        action="metric.update",
        method="PATCH",
        path=request.url.path,
        status_code=200,
        detail={"metric_id": metric_id},
        ip=request.client.host if request.client else "",
    )
    return result
