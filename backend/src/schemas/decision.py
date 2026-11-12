"""决策记录 schema。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DecisionCreate(BaseModel):
    decision: Literal["ship", "kill", "continue"]
    rationale: str = Field(min_length=20, max_length=2000)
    guard_ack: bool = False


class DecisionOut(BaseModel):
    id: int
    experiment_id: int
    experiment_code: str | None = None
    experiment_name: str | None = None
    run_id: int
    run_code: str | None = None
    verdict: str | None = None
    decision: str
    rationale: str
    reviewer: str
    guard_ack: bool
    created_at: datetime
