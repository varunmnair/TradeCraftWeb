"""Add entry strategies tables.

Revision ID: 20240310_0004
Revises: 20240310_0003
Create Date: 2024-03-10 00:04:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20240310_0004"
down_revision = "20240310_0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "entry_strategies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("symbol", sa.String(50), nullable=False),
        sa.Column("dynamic_averaging_enabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("averaging_rules_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_entry_strategies_symbol", "entry_strategies", ["symbol"])

    op.create_table(
        "entry_levels",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("strategy_id", sa.Integer(), sa.ForeignKey("entry_strategies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("level_no", sa.Integer(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "entry_strategy_uploads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("symbols_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("entry_strategy_uploads")
    op.drop_table("entry_levels")
    op.drop_index("ix_entry_strategies_symbol", "entry_strategies")
    op.drop_table("entry_strategies")
