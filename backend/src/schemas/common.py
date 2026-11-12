"""通用 schema：健康检查、概览、错误体。"""
from __future__ import annotations

from pydantic import BaseModel


class HealthOut(BaseModel):
    status: str
    service: str
    version: str
    database: str
    redis: str


class OverviewOut(BaseModel):
    experiments: int
    running: int
    analyzing: int
    decided: int
    runs: int
    assignments: int
    metrics: int
    pending_decisions: int
    worker_heartbeat_age: float | None
    srm_alerts: int


class ErrorOut(BaseModel):
    code: str
    message: str
    detail: str | None = None
