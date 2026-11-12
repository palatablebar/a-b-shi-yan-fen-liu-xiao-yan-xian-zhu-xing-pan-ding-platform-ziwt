"""分桶与分层 schema。"""
from __future__ import annotations

from pydantic import BaseModel


class VariantBucket(BaseModel):
    variant_code: str
    variant_name: str
    is_control: bool
    users: int
    exposures: int
    observed_share: float
    expected_share: float
    deviation_pp: float


class AssignmentSummary(BaseModel):
    experiment_id: int
    unit: str
    total_users: int
    total_exposures: int
    variants: list[VariantBucket]
    srm: dict | None


class SegmentCellOut(BaseModel):
    segment_city: str
    segment_tenure: str
    control_n: int
    treat_n: int
    control_rate: float | None = None
    treat_rate: float | None = None
    lift: float | None = None
    p_value: float | None = None
    q_value: float | None = None
    significant_raw: bool = False
    significant_bh: bool = False
    note: str = ""
