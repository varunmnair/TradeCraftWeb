"""Add session_holdings table for session-scoped holdings persistence"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import Index, UniqueConstraint


revision = '002_add_session_holdings'
down_revision = '71fe80853a0c'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'session_holdings',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(36), nullable=False),
        sa.Column('symbol', sa.String(50), nullable=False),
        sa.Column('exchange', sa.String(10), nullable=True, server_default='NSE'),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('average_price', sa.Float(), nullable=False, server_default='0'),
        sa.Column('last_price', sa.Float(), nullable=True),
        sa.Column('invested', sa.Float(), nullable=True),
        sa.Column('pnl', sa.Float(), nullable=True),
        sa.Column('pnl_pct', sa.Float(), nullable=True),
        sa.Column('quality', sa.String(20), nullable=True),
        sa.Column('exchange_token', sa.String(50), nullable=True),
        sa.Column('instrument_token', sa.String(50), nullable=True),
        sa.Column('isin', sa.String(50), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        UniqueConstraint('session_id', 'symbol', 'exchange', name='uq_session_holding_symbol'),
    )
    op.create_index('ix_session_holdings_session', 'session_holdings', ['session_id'])


def downgrade():
    op.drop_index('ix_session_holdings_session', 'session_holdings')
    op.drop_table('session_holdings')
