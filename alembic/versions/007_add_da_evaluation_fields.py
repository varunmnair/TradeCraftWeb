"""Add DA evaluation fields to entry_strategies

Revision ID: 007_add_da_evaluation_fields
Revises: 006_add_entry_strategy_enhancements
Create Date: 2026-07-07 18:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "007_add_da_evaluation_fields"
down_revision = "006_add_entry_strategy_enhancements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("entry_strategies", sa.Column("da_eligible", sa.Boolean(), nullable=True))
    op.add_column("entry_strategies", sa.Column("da_status", sa.String(30), nullable=True))
    op.add_column("entry_strategies", sa.Column("da_last_evaluated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("entry_strategies", sa.Column("da_confidence_score", sa.Integer(), nullable=True))
    op.add_column("entry_strategies", sa.Column("da_notes", sa.Text(), nullable=True))
    op.add_column("entry_strategies", sa.Column("override_da_enabled", sa.Boolean(), nullable=True))
    op.add_column("entry_strategies", sa.Column("override_da_qty_pct", sa.Float(), nullable=True))
    op.add_column("entry_strategies", sa.Column("override_sell_offset", sa.Float(), nullable=True))
    op.add_column("entry_strategies", sa.Column("override_buyback_price", sa.Float(), nullable=True))
    op.add_column("entry_strategies", sa.Column("override_sell_price", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("entry_strategies", "override_sell_price")
    op.drop_column("entry_strategies", "override_buyback_price")
    op.drop_column("entry_strategies", "override_sell_offset")
    op.drop_column("entry_strategies", "override_da_qty_pct")
    op.drop_column("entry_strategies", "override_da_enabled")
    op.drop_column("entry_strategies", "da_notes")
    op.drop_column("entry_strategies", "da_confidence_score")
    op.drop_column("entry_strategies", "da_last_evaluated_at")
    op.drop_column("entry_strategies", "da_status")
    op.drop_column("entry_strategies", "da_eligible")
