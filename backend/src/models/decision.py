"""决策记录：上线 / 下线 / 继续观察 + 理由 + 复核人。"""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class Decision(Base, TimestampMixin):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    experiment_id: Mapped[int] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    decision: Mapped[str] = mapped_column(String(16), nullable=False)   # ship / kill / continue
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    reviewer: Mapped[str] = mapped_column(String(160), nullable=False)
    guard_ack: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    exported_formats: Mapped[list | None] = mapped_column(JSON, nullable=True)

    experiment = relationship("Experiment", back_populates="decisions")
    run = relationship("AnalysisRun", back_populates="decisions")
