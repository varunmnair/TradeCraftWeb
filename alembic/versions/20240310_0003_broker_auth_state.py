"""Add broker auth state table."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20240310_0003"
down_revision = "20240310_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "broker_auth_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("connection_id", sa.Integer(), sa.ForeignKey("broker_connections.id"), nullable=False),
        sa.Column("broker_name", sa.String(50), nullable=False),
        sa.Column("state_token", sa.String(255), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("broker_auth_states")
