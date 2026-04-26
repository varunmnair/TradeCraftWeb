"""Add captured_at to user_trades and create trade_sync_metadata table"""

from alembic import op
import sqlalchemy as sa


revision = '004_add_capture_tracking'
down_revision = '003_remove_unexpected_user_trades_constraint'
branch_labels = None
depends_on = None


def upgrade():
    # Add captured_at column to user_trades
    op.add_column('user_trades', sa.Column('captured_at', sa.DateTime(timezone=True), nullable=True))
    
    # Add capture_source column to user_trades
    op.add_column('user_trades', sa.Column('capture_source', sa.String(20), nullable=True))
    
    # Create trade_sync_metadata table
    op.create_table(
        'trade_sync_metadata',
        sa.Column('user_id', sa.Integer, nullable=False),
        sa.Column('broker', sa.String(20), nullable=False),
        sa.Column('last_capture_date', sa.Date, nullable=True),
        sa.Column('last_capture_trade_count', sa.Integer, nullable=True),
        sa.Column('last_updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('user_id', 'broker')
    )


def downgrade():
    op.drop_table('trade_sync_metadata')
    op.drop_column('user_trades', 'capture_source')
    op.drop_column('user_trades', 'captured_at')
