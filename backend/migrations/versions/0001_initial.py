"""初始表结构：直接由 SQLAlchemy metadata 建表，避免模型与迁移手抄漂移。

Revision ID: 0001_initial
"""
from __future__ import annotations

from alembic import op

from src.models import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
