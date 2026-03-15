"""Add entry strategy versions table.

Revision ID: 20240310_0005
Revises: 20240310_0004
Create Date: 2024-03-10 00:05:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20240310_0005"
down_revision = "20240310_0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "entry_strategy_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("strategy_id", sa.Integer(), sa.ForeignKey("entry_strategies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("levels_snapshot_json", sa.Text(), nullable=False),
        sa.Column("changes_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("entry_strategy_versions")
