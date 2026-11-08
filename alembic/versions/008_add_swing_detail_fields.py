"""Add swing detail fields to entry_strategies

Revision ID: 008_add_swing_detail_fields
Revises: 007_add_da_evaluation_fields
Create Date: 2026-07-10 12:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "008_add_swing_detail_fields"
down_revision = "007_add_da_evaluation_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("entry_strategies", sa.Column("swing_avg_volume", sa.Float(), nullable=True))
    op.add_column("entry_strategies", sa.Column("swing_atr_percent", sa.Float(), nullable=True))
    op.add_column("entry_strategies", sa.Column("swing_range_percent", sa.Float(), nullable=True))
    op.add_column("entry_strategies", sa.Column("swing_reasons", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("entry_strategies", "swing_reasons")
    op.drop_column("entry_strategies", "swing_range_percent")
    op.drop_column("entry_strategies", "swing_atr_percent")
    op.drop_column("entry_strategies", "swing_avg_volume")
