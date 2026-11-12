"""实验变体（对照组 + 处理组），承载流量配比。"""
from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class Variant(Base, TimestampMixin):
    __tablename__ = "variants"
    __table_args__ = (UniqueConstraint("experiment_id", "code", name="uq_variant_exp_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    experiment_id: Mapped[int] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(24), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    traffic_allocation: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    is_control: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str] = mapped_column(String(240), nullable=False, default="")

    experiment = relationship("Experiment", back_populates="variants")
