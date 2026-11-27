"""Add global UI page configuration table

Revision ID: 011_add_ui_page_configuration
Revises: 010_dedupe_broker_connections
Create Date: 2026-11-26 12:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "011_add_ui_page_configuration"
down_revision = "010_dedupe_broker_connections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ui_page_configurations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("page_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("configuration_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("page_id", name="uq_ui_page_configuration_page_id"),
    )


def downgrade() -> None:
    op.drop_table("ui_page_configurations")