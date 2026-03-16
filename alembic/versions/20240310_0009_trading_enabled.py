"""Add trading_enabled to users table.

Revision ID: 20240310_0009
Revises: 20240310_0008
Create Date: 2024-03-16 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '20240310_0009'
down_revision = '20240310_0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('trading_enabled', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('users', 'trading_enabled')
