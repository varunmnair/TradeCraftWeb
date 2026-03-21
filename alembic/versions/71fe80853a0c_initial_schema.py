"""Initial schema - all tables from db/models.py"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import Index, UniqueConstraint


revision = '71fe80853a0c'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('first_name', sa.String(100), nullable=True),
        sa.Column('last_name', sa.String(100), nullable=True),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('role', sa.String(32), nullable=False, server_default='user'),
        sa.Column('trading_enabled', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        'user_identities',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False, server_default='password'),
        sa.Column('password_hash', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('token_hash', sa.String(255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
    )

    op.create_table(
        'broker_connections',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('broker_name', sa.String(50), nullable=False),
        sa.Column('broker_user_id', sa.String(255), nullable=True),
        sa.Column('encrypted_tokens', sa.LargeBinary(), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('token_updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        UniqueConstraint('user_id', 'broker_name', 'broker_user_id', name='uq_user_broker_broker_user_id'),
    )

    op.create_table(
        'jobs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('session_id', sa.String(255), nullable=False),
        sa.Column('job_type', sa.String(100), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('progress', sa.Float(), nullable=False, server_default='0'),
        sa.Column('log', sa.Text(), nullable=True),
        sa.Column('payload_json', sa.Text(), nullable=True),
        sa.Column('result_json', sa.Text(), nullable=True),
        sa.Column('error_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        'audit_events',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('action', sa.String(255), nullable=False),
        sa.Column('resource_type', sa.String(100), nullable=False),
        sa.Column('resource_id', sa.String(255), nullable=True),
        sa.Column('broker_connection_id', sa.Integer(), sa.ForeignKey('broker_connections.id'), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('request_id', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'broker_auth_states',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('connection_id', sa.Integer(), sa.ForeignKey('broker_connections.id'), nullable=False),
        sa.Column('broker_name', sa.String(50), nullable=False),
        sa.Column('state_token', sa.String(255), nullable=False, unique=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'entry_strategies',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('symbol', sa.String(50), nullable=False),
        sa.Column('broker', sa.String(20), nullable=True),
        sa.Column('broker_user_id', sa.String(50), nullable=True),
        sa.Column('allocated', sa.Float(), nullable=True),
        sa.Column('quality', sa.String(50), nullable=True),
        sa.Column('exchange', sa.String(10), nullable=True),
        sa.Column('dynamic_averaging_enabled', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('averaging_rules_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_entry_strategies_symbol', 'entry_strategies', ['symbol'])

    op.create_table(
        'entry_levels',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('strategy_id', sa.Integer(), sa.ForeignKey('entry_strategies.id'), nullable=False),
        sa.Column('level_no', sa.Integer(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        'entry_strategy_uploads',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('symbols_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'entry_strategy_versions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('strategy_id', sa.Integer(), sa.ForeignKey('entry_strategies.id'), nullable=False),
        sa.Column('version_no', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('levels_snapshot_json', sa.Text(), nullable=False),
        sa.Column('changes_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'market_universe',
        sa.Column('symbol', sa.String(50), primary_key=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('universe', sa.String(50), nullable=False, server_default='NIFTY500'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        'market_quotes_daily',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('symbol', sa.String(50), nullable=False),
        sa.Column('trade_date', sa.String(10), nullable=False),
        sa.Column('cmp', sa.Float(), nullable=True),
        sa.Column('as_of_ts', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source', sa.String(20), nullable=True),
        UniqueConstraint('symbol', 'trade_date', name='uq_symbol_trade_date'),
    )

    op.create_table(
        'market_candles_daily',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('symbol', sa.String(50), nullable=False),
        sa.Column('trade_date', sa.String(10), nullable=False),
        sa.Column('open', sa.Float(), nullable=True),
        sa.Column('high', sa.Float(), nullable=True),
        sa.Column('low', sa.Float(), nullable=True),
        sa.Column('close', sa.Float(), nullable=True),
        sa.Column('volume', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(20), nullable=True),
        UniqueConstraint('symbol', 'trade_date', name='uq_candle_symbol_trade_date'),
    )

    op.create_table(
        'symbol_catalog',
        sa.Column('symbol', sa.String(50), primary_key=True),
        sa.Column('company_name', sa.String(255), nullable=False),
        sa.Column('series', sa.String(10), nullable=False),
        sa.Column('isin', sa.String(20), nullable=False),
        sa.Column('exchange', sa.String(10), nullable=False, server_default='NSE'),
        sa.Column('cmp', sa.Float(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'ohlcv_daily',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('symbol', sa.String(50), nullable=False),
        sa.Column('trade_date', sa.Date(), nullable=False),
        sa.Column('open', sa.Float(), nullable=True),
        sa.Column('high', sa.Float(), nullable=True),
        sa.Column('low', sa.Float(), nullable=True),
        sa.Column('close', sa.Float(), nullable=True),
        sa.Column('volume', sa.Integer(), nullable=True),
        UniqueConstraint('symbol', 'trade_date', name='uq_ohlcv_symbol_trade_date'),
    )
    op.create_index('ix_ohlcv_symbol_trade_date', 'ohlcv_daily', [sa.text('symbol'), sa.text('trade_date DESC')])

    op.create_table(
        'user_trades',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(36), nullable=True),
        sa.Column('broker', sa.String(20), nullable=False),
        sa.Column('symbol', sa.String(50), nullable=False),
        sa.Column('isin', sa.String(50), nullable=True),
        sa.Column('trade_date', sa.String(10), nullable=False),
        sa.Column('exchange', sa.String(10), nullable=True),
        sa.Column('segment', sa.String(10), nullable=True),
        sa.Column('series', sa.String(10), nullable=True),
        sa.Column('side', sa.String(10), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('trade_id', sa.String(50), nullable=True),
        sa.Column('order_id', sa.String(50), nullable=True),
        sa.Column('order_execution_time', sa.String(50), nullable=True),
        sa.Column('source', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        UniqueConstraint('user_id', 'broker', 'trade_id', name='uq_user_broker_trade_id'),
    )
    op.create_index('ix_user_trades_session_id', 'user_trades', ['session_id'])
    op.create_index('ix_user_trades_symbol', 'user_trades', ['symbol'])
    op.create_index('ix_user_trades_trade_date', 'user_trades', ['trade_date'])
    op.create_index('ix_trades_session_symbol', 'user_trades', ['session_id', 'symbol'])


def downgrade():
    op.drop_table('user_trades')
    op.drop_table('ohlcv_daily')
    op.drop_table('symbol_catalog')
    op.drop_table('market_candles_daily')
    op.drop_table('market_quotes_daily')
    op.drop_table('market_universe')
    op.drop_table('entry_strategy_versions')
    op.drop_table('entry_strategy_uploads')
    op.drop_table('entry_levels')
    op.drop_table('entry_strategies')
    op.drop_table('broker_auth_states')
    op.drop_table('audit_events')
    op.drop_table('jobs')
    op.drop_table('broker_connections')
    op.drop_table('refresh_tokens')
    op.drop_table('user_identities')
    op.drop_table('users')
