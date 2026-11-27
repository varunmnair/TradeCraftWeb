"""Deduplicate broker connections to one row per user and broker

Revision ID: 010_dedupe_broker_connections
Revises: 009_add_order_placements
Create Date: 2026-11-26 09:00:00.000000

"""

from __future__ import annotations

from collections import defaultdict

import sqlalchemy as sa

from alembic import op

revision = "010_dedupe_broker_connections"
down_revision = "009_add_order_placements"
branch_labels = None
depends_on = None


_CONNECTIONS = sa.table(
    "broker_connections",
    sa.column("id", sa.Integer()),
    sa.column("user_id", sa.Integer()),
    sa.column("broker_name", sa.String()),
    sa.column("broker_user_id", sa.String()),
    sa.column("encrypted_tokens", sa.LargeBinary()),
    sa.column("token_updated_at", sa.DateTime()),
)
_AUTH_STATES = sa.table(
    "broker_auth_states",
    sa.column("id", sa.Integer()),
    sa.column("connection_id", sa.Integer()),
)
_AUDIT_EVENTS = sa.table(
    "audit_events",
    sa.column("id", sa.Integer()),
    sa.column("broker_connection_id", sa.Integer()),
)
_ORDER_PLACEMENTS = sa.table(
    "order_placements",
    sa.column("id", sa.Integer()),
    sa.column("broker_connection_id", sa.Integer()),
)


def _rank(row):
    """Prefer a row with tokens, then an identity, then the newest row."""
    return (
        row.encrypted_tokens is not None,
        row.broker_user_id is not None,
        row.token_updated_at is not None,
        row.id,
    )


def upgrade() -> None:
    """Remove duplicate and abandoned placeholder connections.

    The unique key allows unlimited ``NULL`` identities, so interrupted OAuth
    flows left one empty row per click. Keep the most useful row per
    ``(user_id, broker_name)`` and drop the rest, including rows that never
    received tokens or an identity.
    """
    bind = op.get_bind()
    rows = bind.execute(sa.select(_CONNECTIONS)).fetchall()

    groups = defaultdict(list)
    for row in rows:
        groups[(row.user_id, row.broker_name)].append(row)

    stale_ids: set[int] = set()
    for group in groups.values():
        keeper = group[0]
        for row in group[1:]:
            if _rank(row) > _rank(keeper):
                keeper = row
        stale_ids.update(row.id for row in group if row.id != keeper.id)

    for row in rows:
        if row.encrypted_tokens is None and row.broker_user_id is None:
            stale_ids.add(row.id)

    if not stale_ids:
        return

    ids = list(stale_ids)
    bind.execute(sa.delete(_AUTH_STATES).where(_AUTH_STATES.c.connection_id.in_(ids)))
    bind.execute(
        sa.update(_AUDIT_EVENTS)
        .where(_AUDIT_EVENTS.c.broker_connection_id.in_(ids))
        .values(broker_connection_id=None)
    )
    if sa.inspect(bind).has_table("order_placements"):
        bind.execute(
            sa.update(_ORDER_PLACEMENTS)
            .where(_ORDER_PLACEMENTS.c.broker_connection_id.in_(ids))
            .values(broker_connection_id=None)
        )
    bind.execute(sa.delete(_CONNECTIONS).where(_CONNECTIONS.c.id.in_(ids)))


def downgrade() -> None:
    """Deleted connection rows cannot be restored."""
