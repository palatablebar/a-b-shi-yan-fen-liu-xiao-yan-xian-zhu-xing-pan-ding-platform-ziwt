"""指标路由：读全角色；改口径仅 admin。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import metric_controller
from src.middlewares.rbac import require_permission
from src.models.user import User
from src.schemas.metric import MetricOut, MetricUpdate

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("", response_model=list[MetricOut])
def list_metrics(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("metrics:read")),
) -> list[MetricOut]:
    return metric_controller.list_metrics(db)


@router.patch("/{metric_id}", response_model=MetricOut)
def update_metric(
    metric_id: int,
    payload: MetricUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("metrics:write")),
) -> MetricOut:
    return metric_controller.update_metric(metric_id, payload, request, db, user)
