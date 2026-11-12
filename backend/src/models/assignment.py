"""分桶曝光记录：一个用户一条，exposure_count 为窗口内曝光次数（SRM 口径）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (
        UniqueConstraint("experiment_id", "user_key", name="uq_assignment_exp_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    experiment_id: Mapped[int] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    variant_id: Mapped[int] = mapped_column(ForeignKey("variants.id"), nullable=False, index=True)
    user_key: Mapped[str] = mapped_column(String(64), nullable=False)
    bucket: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    exposure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    segment_city: Mapped[str] = mapped_column(String(24), nullable=False, default="一线")
    segment_tenure: Mapped[str] = mapped_column(String(24), nullable=False, default="新客")
    flags: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metric_value: Mapped[float] = mapped_column(Numeric(14, 6), nullable=False, default=0.0)
    exposed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
