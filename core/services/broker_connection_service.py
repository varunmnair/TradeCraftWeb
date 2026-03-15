"""Broker connection persistence service."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from core.security.encryption import get_encryptor
from db import models
from db.database import SessionLocal


class BrokerConnectionService:
    def __init__(self, session_factory=SessionLocal):
        self._session_factory = session_factory
        self._encryptor = get_encryptor()

    def create_connection(
        self,
        *,
        tenant_id: int,
        user_id: int,
        broker_name: str,
        tokens: Dict[str, Any] | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> models.BrokerConnection:
        metadata_json = json.dumps(metadata or {})
        encrypted = self._encryptor.encrypt_dict(tokens or {}) if tokens else None
        with self._session_factory() as session:
            connection = models.BrokerConnection(
                tenant_id=tenant_id,
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
        tenant_id: int,
        user_id: int,
        broker_name: str,
        connection_id: int | None = None,
        allow_admin: bool = False,
    ) -> models.BrokerConnection:
        broker_name = broker_name.lower()
        with self._session_factory() as session:
            if connection_id is not None:
                connection = session.get(models.BrokerConnection, connection_id)
                if not connection:
                    raise ValueError("Broker connection not found")
                if connection.tenant_id != tenant_id:
                    raise ValueError("Connection belongs to another tenant")
                if (not allow_admin) and connection.user_id != user_id:
                    raise ValueError("Connection belongs to another user")
                if connection.broker_name != broker_name:
                    raise ValueError("Connection broker mismatch")
                return connection
            connection = models.BrokerConnection(
                tenant_id=tenant_id,
                user_id=user_id,
                broker_name=broker_name,
                metadata_json=json.dumps({}),
            )
            session.add(connection)
            session.commit()
            session.refresh(connection)
            return connection

    def list_connections(self, tenant_id: int, user_id: int | None = None) -> List[models.BrokerConnection]:
        with self._session_factory() as session:
            query = session.query(models.BrokerConnection).filter(models.BrokerConnection.tenant_id == tenant_id)
            if user_id is not None:
                query = query.filter(models.BrokerConnection.user_id == user_id)
            return query.order_by(models.BrokerConnection.created_at.desc()).all()

    def get_connection(self, connection_id: int) -> models.BrokerConnection | None:
        with self._session_factory() as session:
            return session.get(models.BrokerConnection, connection_id)

    def get_active_connection(
        self,
        *,
        tenant_id: int,
        user_id: int,
        broker_name: str,
        token_bundle,
    ) -> models.BrokerConnection | None:
        """
        Find an active connection for the given user and broker.
        A connection is considered active if token_bundle returns non-None.
        """
        broker_name = broker_name.lower()
        connections = self.list_connections(tenant_id=tenant_id, user_id=user_id)
        for conn in connections:
            if conn.broker_name == broker_name:
                if token_bundle(broker_name, connection_id=conn.id):
                    return conn
        return None
