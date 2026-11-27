"""Broker connection persistence service."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from core.security.encryption import get_encryptor
from db import models
from db.database import SessionLocal


def release_broker_identity(session, *, connection, broker_user_id: str) -> bool:
    """Free a broker identity before assigning it to ``connection``.

    SQLAlchemy flushes UPDATEs before DELETEs, so deleting a conflicting row in
    the same flush would still trip ``uq_user_broker_broker_user_id``. Clear the
    identity (and the stale tokens that go with it) on every conflicting row and
    flush first. Returns True when a conflict was cleared.
    """
    query = session.query(models.BrokerConnection).filter(
        models.BrokerConnection.user_id == connection.user_id,
        models.BrokerConnection.broker_name == connection.broker_name,
        models.BrokerConnection.broker_user_id == broker_user_id,
    )
    if connection.id is not None:
        query = query.filter(models.BrokerConnection.id != connection.id)

    conflicts = query.all()
    for conflict in conflicts:
        conflict.broker_user_id = None
        conflict.encrypted_tokens = None
        conflict.token_updated_at = None
    if conflicts:
        session.flush()
    return bool(conflicts)


class BrokerConnectionService:
    def __init__(self, session_factory=SessionLocal):
        self._session_factory = session_factory
        self._encryptor = get_encryptor()

    def create_connection(
        self,
        *,
        user_id: int,
        broker_name: str,
        tokens: Dict[str, Any] | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> models.BrokerConnection:
        metadata_json = json.dumps(metadata or {})
        encrypted = self._encryptor.encrypt_dict(tokens or {}) if tokens else None
        with self._session_factory() as session:
            connection = models.BrokerConnection(
                user_id=user_id,
                broker_name=broker_name.lower(),
                encrypted_tokens=encrypted,
                metadata_json=metadata_json,
            )
            session.add(connection)
            session.commit()
            session.refresh(connection)
            return connection

    def ensure_connection(
        self,
        *,
        user_id: int,
        broker_name: str,
        connection_id: int | None = None,
        allow_admin: bool = False,
    ) -> models.BrokerConnection:
        broker_name = broker_name.lower()
        with self._session_factory() as session:
            if connection_id is not None:
                connection = session.get(models.BrokerConnection, connection_id)
                if connection:
                    foreign = (not allow_admin) and connection.user_id != user_id
                    wrong_broker = connection.broker_name != broker_name
                    if not foreign and not wrong_broker:
                        return connection
                # A stale, deleted, foreign, or wrong-broker id (typically left
                # in localStorage by another account) falls back to the user's
                # own current connection instead of failing the connect call.

            # One connection per user and broker: reconnecting refreshes the
            # existing row instead of inserting another empty (NULL-identity)
            # record. Prefer a row that already has tokens over an orphaned
            # placeholder left behind by an interrupted OAuth flow.
            connection = (
                session.query(models.BrokerConnection)
                .filter(
                    models.BrokerConnection.user_id == user_id,
                    models.BrokerConnection.broker_name == broker_name,
                )
                .order_by(
                    models.BrokerConnection.encrypted_tokens.is_(None).asc(),
                    models.BrokerConnection.id.desc(),
                )
                .first()
            )
            if connection is None:
                connection = models.BrokerConnection(
                    user_id=user_id,
                    broker_name=broker_name,
                    metadata_json=json.dumps({}),
                )
                session.add(connection)
                session.commit()
                session.refresh(connection)
            return connection

    def set_broker_user_id(
        self, *, connection_id: int, broker_user_id: str
    ) -> models.BrokerConnection | None:
        """Set a broker identity without colliding with an existing connection."""
        with self._session_factory() as session:
            connection = session.get(models.BrokerConnection, connection_id)
            if not connection:
                return None
            release_broker_identity(
                session, connection=connection, broker_user_id=broker_user_id
            )
            connection.broker_user_id = broker_user_id
            session.commit()
            session.refresh(connection)
            return connection

    def list_connections(
        self, user_id: int | None = None
    ) -> List[models.BrokerConnection]:
        with self._session_factory() as session:
            query = session.query(models.BrokerConnection)
            if user_id is not None:
                query = query.filter(models.BrokerConnection.user_id == user_id)
            return query.order_by(models.BrokerConnection.created_at.desc()).all()

    def get_connection(self, connection_id: int) -> models.BrokerConnection | None:
        with self._session_factory() as session:
            return session.get(models.BrokerConnection, connection_id)

    @staticmethod
    def _bundle_is_valid(bundle) -> bool:
        if bundle is None or not getattr(bundle, "access_token", None):
            return False
        expires_at = getattr(bundle, "expires_at", None)
        if expires_at is None:
            return True
        try:
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            return expires_at > datetime.now(timezone.utc)
        except Exception:
            return True

    def get_active_connection(
        self,
        *,
        user_id: int,
        broker_name: str,
        token_bundle,
    ) -> models.BrokerConnection | None:
        """
        Find an active connection for the given user and broker.
        A connection is considered active if its token bundle is present and not expired.
        """
        broker_name = broker_name.lower()
        connections = self.list_connections(user_id=user_id)
        for conn in connections:
            if conn.broker_name == broker_name:
                bundle = token_bundle(broker_name, connection_id=conn.id)
                if self._bundle_is_valid(bundle):
                    return conn
        return None
