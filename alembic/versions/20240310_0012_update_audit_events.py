"""Update audit_events with new fields."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20240310_0012"
down_revision = "20240310_0011"
branch_labels = None
depends_on = None


def upgrade():
    # Check existing columns first
    # Add new columns if they don't exist
    op.add_column("audit_events", sa.Column("metadata_json", sa.Text(), nullable=True))
    op.add_column("audit_events", sa.Column("ip_address", sa.String(length=45), nullable=True))
    op.add_column("audit_events", sa.Column("user_agent", sa.String(length=500), nullable=True))
    op.add_column("audit_events", sa.Column("request_id", sa.String(length=100), nullable=True))
    
    # Rename columns
    op.alter_column("audit_events", "entity_type", new_column_name="resource_type")
    op.alter_column("audit_events", "entity_id", new_column_name="resource_id")
    
    # Drop old columns (if they exist)
    try:
        op.drop_column("audit_events", "request_json")
    except Exception:
        pass
    try:
        op.drop_column("audit_events", "response_json")
    except Exception:
        pass


def downgrade():
    op.add_column("audit_events", sa.Column("response_json", sa.Text(), nullable=True))
    op.add_column("audit_events", sa.Column("request_json", sa.Text(), nullable=True))
    
    op.alter_column("audit_events", "resource_type", new_column_name="entity_type")
    op.alter_column("audit_events", "resource_id", new_column_name="entity_id")
    
    op.drop_column("audit_events", "request_id")
    op.drop_column("audit_events", "user_agent")
    op.drop_column("audit_events", "ip_address")
    op.drop_column("audit_events", "metadata_json")
