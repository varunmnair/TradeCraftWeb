"""Add is_premium column to users table"""

from alembic import op
import sqlalchemy as sa


revision = '005_add_is_premium'
down_revision = '004_add_capture_tracking'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('is_premium', sa.Boolean(), nullable=False, server_default=sa.text('0')))


def downgrade():
    op.drop_column('users', 'is_premium')
