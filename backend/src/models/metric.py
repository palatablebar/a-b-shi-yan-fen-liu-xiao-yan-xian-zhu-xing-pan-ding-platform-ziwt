"""指标定义：主指标 / 守卫指标 / 辅助指标，比例或均值口径。"""
from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class Metric(Base, TimestampMixin):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)          # ratio / mean
    role: Mapped[str] = mapped_column(String(16), nullable=False)          # primary / guard / secondary
    direction: Mapped[str] = mapped_column(String(24), nullable=False)     # increase_good / decrease_good
    unit: Mapped[str] = mapped_column(String(24), nullable=False, default="%")
    definition: Mapped[str] = mapped_column(Text, nullable=False, default="")
