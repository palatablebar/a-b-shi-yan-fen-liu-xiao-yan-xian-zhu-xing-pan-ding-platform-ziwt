"""实验：主指标、守卫指标、显著性参数与状态机。"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, utcnow


class Experiment(Base, TimestampMixin):
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    owner_name: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft", index=True)
    primary_metric_id: Mapped[int | None] = mapped_column(
        ForeignKey("metrics.id"), nullable=True
    )
    guard_metric_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    secondary_metric_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    alpha: Mapped[float] = mapped_column(Float, nullable=False, default=0.05)
    srm_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.001)
    min_sample_per_arm: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    primary_metric = relationship("Metric", foreign_keys=[primary_metric_id], lazy="joined")
    variants = relationship(
        "Variant", back_populates="experiment", cascade="all, delete-orphan", lazy="selectin"
    )
    runs = relationship(
        "AnalysisRun", back_populates="experiment", cascade="all, delete-orphan", lazy="selectin"
    )
    decisions = relationship(
        "Decision", back_populates="experiment", cascade="all, delete-orphan", lazy="selectin"
    )
