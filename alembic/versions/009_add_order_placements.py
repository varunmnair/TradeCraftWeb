"""Add durable order placement idempotency records

Revision ID: 009_add_order_placements
Revises: 008_add_swing_detail_fields
Create Date: 2026-11-21 12:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "009_add_order_placements"
down_revision = "008_add_swing_detail_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Dev/prod startup calls Base.metadata.create_all(), so the table can
    # already exist on databases whose revision has not been stamped yet.
    op.create_table(
        "order_placements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("session_id", sa.String(255), nullable=False),
        sa.Column("broker_name", sa.String(50), nullable=True),
        sa.Column("broker_connection_id", sa.Integer(), nullable=True),
        sa.Column("device_id", sa.String(100), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="in_flight"),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("error_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_order_placement_user_key"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_order_placements_session",
        "order_placements",
        ["session_id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_order_placements_session", table_name="order_placements")
    op.drop_table("order_placements")
