"""多臂实验：analysis_runs 增加 arms JSON 列（逐方案结果，兼容旧两臂批次）。

Revision ID: 0002_multi_arm
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_multi_arm"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analysis_runs", sa.Column("arms", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("analysis_runs", "arms")
