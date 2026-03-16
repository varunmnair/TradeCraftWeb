"""Add payload_json column to jobs table."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20240310_0011"
down_revision = "20240310_0009"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("jobs", sa.Column("payload_json", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("jobs", "payload_json")
