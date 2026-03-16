"""Add user identity and refresh token tables.

Revision ID: 20240310_0008
Revises: 20240310_0007
Create Date: 2024-03-10 00:07:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20240310_0008'
down_revision = '20240310_0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Note: first_name, last_name, phone, updated_at columns are now in the initial migration
    # Create user_identities table
    op.create_table(
        'user_identities',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False, server_default='password'),
        sa.Column('password_hash', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_user_identities_user_id', 'user_identities', ['user_id'])
    
    # Create refresh_tokens table
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
    op.create_index('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id'])
    op.create_index('ix_refresh_tokens_token_hash', 'refresh_tokens', ['token_hash'])


def downgrade() -> None:
    op.drop_index('ix_refresh_tokens_token_hash', 'refresh_tokens')
    op.drop_index('ix_refresh_tokens_user_id', 'refresh_tokens')
    op.drop_table('refresh_tokens')
    
    op.drop_index('ix_user_identities_user_id', 'user_identities')
    op.drop_table('user_identities')
    
    op.drop_column('users', 'phone')
    op.drop_column('users', 'last_name')
    op.drop_column('users', 'first_name')
    op.drop_column('users', 'updated_at')
