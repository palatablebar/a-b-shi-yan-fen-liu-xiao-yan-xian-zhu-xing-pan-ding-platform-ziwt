"""分析批次：一次真算的完整结果（SRM / 指标对比 / 分层 / BH / 守卫 / 结论）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, utcnow


class AnalysisRun(Base, TimestampMixin):
    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    experiment_id: Mapped[int] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_code: Mapped[str] = mapped_column(String(48), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    triggered_by: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    srm: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metrics: Mapped[list | None] = mapped_column(JSON, nullable=True)
    strata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    comparisons: Mapped[list | None] = mapped_column(JSON, nullable=True)
    guard: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 多臂（>2 变体）实验：每个处理方案一条 arm 结果（共同对照、逐臂 SRM/指标/守卫/分层/校正/可上线状态）
    arms: Mapped[list | None] = mapped_column(JSON, nullable=True)
    verdict: Mapped[str | None] = mapped_column(String(16), nullable=True)
    verdict_reasons: Mapped[list | None] = mapped_column(JSON, nullable=True)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    experiment = relationship("Experiment", back_populates="runs")
    decisions = relationship("Decision", back_populates="run", lazy="selectin")
