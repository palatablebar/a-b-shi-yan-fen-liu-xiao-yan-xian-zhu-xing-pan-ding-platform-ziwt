"""指标服务：列表与口径维护（admin 才能改口径）。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.constants import error_codes as codes
from src.models.metric import Metric
from src.schemas.metric import MetricOut, MetricUpdate
from src.utils.errors import AppError

_VALID_ROLES = {"primary", "guard", "secondary"}
_VALID_DIRECTIONS = {"increase_good", "decrease_good"}


class MetricService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_metrics(self) -> list[MetricOut]:
        rows = self.db.query(Metric).order_by(Metric.id.asc()).all()
        return [MetricOut.from_model(m) for m in rows]

    def update(self, metric_id: int, payload: MetricUpdate) -> MetricOut:
        metric = self.db.get(Metric, metric_id)
        if metric is None:
            raise AppError(codes.NOT_FOUND, "指标不存在", f"metric_id={metric_id}", 404)
        if payload.role is not None:
            if payload.role not in _VALID_ROLES:
                raise AppError(codes.VALIDATION_FAILED, "指标角色非法", f"role={payload.role}", 422)
            metric.role = payload.role
        if payload.direction is not None:
            if payload.direction not in _VALID_DIRECTIONS:
                raise AppError(codes.VALIDATION_FAILED, "指标方向非法", f"direction={payload.direction}", 422)
            metric.direction = payload.direction
        if payload.name is not None:
            metric.name = payload.name
        if payload.unit is not None:
            metric.unit = payload.unit
        if payload.definition is not None:
            metric.definition = payload.definition
        self.db.commit()
        self.db.refresh(metric)
        return MetricOut.from_model(metric)
