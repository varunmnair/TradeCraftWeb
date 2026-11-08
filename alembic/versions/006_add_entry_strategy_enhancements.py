"""Add review lifecycle columns to entry_strategies"""

from alembic import op
import sqlalchemy as sa


revision = '006_add_entry_strategy_enhancements'
down_revision = '005_add_is_premium'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('entry_strategies', sa.Column('last_evaluated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('entry_strategies', sa.Column('last_entry_revision_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('entry_strategies', sa.Column('swing_eligible', sa.Boolean(), nullable=True))
    op.add_column('entry_strategies', sa.Column('thesis_break_price', sa.Float(), nullable=True))
    op.add_column('entry_strategies', sa.Column('review_status', sa.String(20), nullable=True, server_default=sa.text("'ACTIVE'")))


def downgrade():
    op.drop_column('entry_strategies', 'review_status')
    op.drop_column('entry_strategies', 'thesis_break_price')
    op.drop_column('entry_strategies', 'swing_eligible')
    op.drop_column('entry_strategies', 'last_entry_revision_at')
    op.drop_column('entry_strategies', 'last_evaluated_at')
