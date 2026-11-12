"""变体 schema。"""
from __future__ import annotations

from pydantic import BaseModel


class VariantOut(BaseModel):
    id: int
    code: str
    name: str
    traffic_allocation: float
    is_control: bool
    description: str
    users: int = 0
    exposures: int = 0

    @classmethod
    def from_model(cls, v, users: int = 0, exposures: int = 0) -> "VariantOut":
        return cls(
            id=v.id,
            code=v.code,
            name=v.name,
            traffic_allocation=v.traffic_allocation,
            is_control=v.is_control,
            description=v.description or "",
            users=users,
            exposures=exposures,
        )
