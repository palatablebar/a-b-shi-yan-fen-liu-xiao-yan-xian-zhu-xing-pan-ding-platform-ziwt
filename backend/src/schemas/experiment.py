"""实验 schema：列表摘要 + 详情（含分流校验快照与最近批次结论）。"""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from src.schemas.metric import MetricOut
from src.schemas.variant import VariantOut


class ExperimentSummary(BaseModel):
    id: int
    code: str
    name: str
    status: str
    owner_name: str
    primary_metric_name: str | None
    start_date: date | None
    end_date: date | None
    variants: int
    assignments: int
    latest_verdict: str | None
    latest_srm: str | None
    latest_run_at: datetime | None = None


class ExperimentDetail(BaseModel):
    id: int
    code: str
    name: str
    hypothesis: str
    description: str
    owner_name: str
    status: str
    alpha: float
    srm_threshold: float
    min_sample_per_arm: int
    start_date: date | None
    end_date: date | None
    notes: str
    created_by: str
    updated_at: datetime
    primary_metric: MetricOut | None
    guard_metrics: list[MetricOut]
    variants: list[VariantOut]
    assignment_total: int
    srm_snapshot: dict | None = None
    latest_run: dict | None = None
    decision: dict | None = None


class VariantCreate(BaseModel):
    code: str = Field(min_length=1, max_length=24, pattern=r"^[a-z0-9_\-]+$")
    name: str = Field(min_length=1, max_length=80)
    traffic_allocation: float = Field(gt=0, lt=1)
    is_control: bool = False
    description: str = Field(default="", max_length=240)


class ExperimentCreate(BaseModel):
    code: str = Field(min_length=3, max_length=48, pattern=r"^[a-z0-9_\-]+$")
    name: str = Field(min_length=2, max_length=160)
    hypothesis: str = Field(default="", max_length=2000)
    description: str = Field(default="", max_length=2000)
    owner_name: str = Field(min_length=1, max_length=80)
    primary_metric_id: int
    guard_metric_ids: list[int] = Field(default_factory=list, max_length=4)
    secondary_metric_ids: list[int] = Field(default_factory=list, max_length=4)
    variants: list[VariantCreate] = Field(default_factory=list, max_length=4)
    start_date: date | None = None
    end_date: date | None = None
    alpha: float = Field(default=0.05, gt=0, lt=0.5)
    srm_threshold: float = Field(default=0.001, gt=0, lt=0.5)
    notes: str = Field(default="", max_length=2000)


class ExperimentUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    hypothesis: str | None = Field(default=None, max_length=2000)
    description: str | None = Field(default=None, max_length=2000)
    owner_name: str | None = Field(default=None, max_length=80)
    status: str | None = None
    primary_metric_id: int | None = None
    guard_metric_ids: list[int] | None = None
    secondary_metric_ids: list[int] | None = None
    alpha: float | None = Field(default=None, gt=0, lt=0.5)
    srm_threshold: float | None = Field(default=None, gt=0, lt=0.5)
    notes: str | None = Field(default=None, max_length=2000)
