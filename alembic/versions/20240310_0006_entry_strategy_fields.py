"""Add allocated, quality, exchange to entry_strategies.

Revision ID: 20240310_0006
Revises: 20240310_0005
Create Date: 2024-03-10 00:06:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20240310_0006"
down_revision = "20240310_0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("entry_strategies", sa.Column("allocated", sa.Float(), nullable=True))
    op.add_column("entry_strategies", sa.Column("quality", sa.String(50), nullable=True))
    op.add_column("entry_strategies", sa.Column("exchange", sa.String(10), nullable=True))


def downgrade():
    op.drop_column("entry_strategies", "exchange")
    op.drop_column("entry_strategies", "quality")
    op.drop_column("entry_strategies", "allocated")
