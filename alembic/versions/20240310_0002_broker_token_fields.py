"""Add broker_user_id and token metadata."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20240310_0002"
down_revision = "20240310_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("broker_connections", sa.Column("broker_user_id", sa.String(length=255), nullable=True))
    op.add_column("broker_connections", sa.Column("token_updated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("broker_connections", "token_updated_at")
    op.drop_column("broker_connections", "broker_user_id")
