"""分析批次 schema。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class RunSummary(BaseModel):
    id: int
    experiment_id: int
    experiment_code: str | None = None
    experiment_name: str | None = None
    run_code: str
    status: str
    verdict: str | None
    locked: bool
    triggered_by: str
    srm_verdict: str | None
    srm_p_value: float | None
    primary_lift: float | None
    primary_p_value: float | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    error: str | None = None


class RunDetail(BaseModel):
    id: int
    experiment_id: int
    run_code: str
    status: str
    verdict: str | None
    locked: bool
    triggered_by: str
    params: dict | None
    srm: dict | None
    metrics: list | None
    strata: dict | None
    comparisons: list | None
    guard: dict | None
    arms: list | None = None
    verdict_reasons: list | None
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    experiment: dict | None = None
