"""Remove unexpected unique constraint from user_trades"""

from alembic import op
import sqlalchemy as sa


revision = '003_remove_unexpected_user_trades_constraint'
down_revision = '002_add_session_holdings'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('DROP INDEX IF EXISTS sqlite_autoindex_user_trades_1')


def downgrade():
    pass
