"""指标 schema。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class MetricOut(BaseModel):
    id: int
    code: str
    name: str
    kind: str
    role: str
    direction: str
    unit: str
    definition: str

    @classmethod
    def from_model(cls, m) -> "MetricOut":
        return cls(
            id=m.id,
            code=m.code,
            name=m.name,
            kind=m.kind,
            role=m.role,
            direction=m.direction,
            unit=m.unit,
            definition=m.definition or "",
        )


class MetricUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    role: str | None = None
    direction: str | None = None
    unit: str | None = Field(default=None, max_length=24)
    definition: str | None = Field(default=None, max_length=400)
