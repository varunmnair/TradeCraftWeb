"""Add broker and broker_user_id to entry_strategies for session scoping.

Revision ID: 20240310_0007
Revises: 20240310_0006
Create Date: 2024-03-14 00:07:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20240310_0007"
down_revision = "20240310_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("entry_strategies", sa.Column("broker", sa.String(20), nullable=True))
    op.add_column("entry_strategies", sa.Column("broker_user_id", sa.String(50), nullable=True))
    
    # Create index for faster lookups by broker scope
    op.create_index("ix_entry_strategies_broker_scope", "entry_strategies", 
                    ["tenant_id", "user_id", "broker", "broker_user_id"])


def downgrade():
    op.drop_index("ix_entry_strategies_broker_scope", table_name="entry_strategies")
    op.drop_column("entry_strategies", "broker_user_id")
    op.drop_column("entry_strategies", "broker")
