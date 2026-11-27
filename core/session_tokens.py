"""Token storage abstractions for CLI vs SaaS."""

from __future__ import annotations

import json
import pickle
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from core.security.encryption import get_encryptor
from core.services.broker_connection_service import release_broker_identity
from db import models
from db.database import SessionLocal


@dataclass
class TokenBundle:
    access_token: str
    extended_token: Optional[str] = None
    broker_user_id: Optional[str] = None
    raw_profile: Optional[Dict[str, Any]] = None
    obtained_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    extras: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_obj(cls, data: Any) -> "TokenBundle":
        if isinstance(data, TokenBundle):
            return data
        if isinstance(data, str):
            return cls(access_token=data)
        if not isinstance(data, dict):
            raise ValueError("Token data must be dict or string")
        known = {
            "access_token",
            "extended_token",
            "broker_user_id",
            "raw_profile",
            "obtained_at",
            "expires_at",
        }
        extras = {k: v for k, v in data.items() if k not in known}
        access = data.get("access_token")
        if not access:
            raise ValueError("Token bundle missing access_token")
        obtained_at = data.get("obtained_at")
        if isinstance(obtained_at, str):
            obtained_at = datetime.fromisoformat(obtained_at)
        expires_at = data.get("expires_at")
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        return cls(
            access_token=access,
            extended_token=data.get("extended_token"),
            broker_user_id=data.get("broker_user_id"),
            raw_profile=data.get("raw_profile"),
            obtained_at=obtained_at or datetime.now(timezone.utc),
            expires_at=expires_at,
            extras=extras,
        )

    def to_payload(self) -> Dict[str, Any]:
        payload = dict(self.extras)
        payload["access_token"] = self.access_token
        if self.extended_token:
            payload["extended_token"] = self.extended_token
        if self.broker_user_id:
            payload["broker_user_id"] = self.broker_user_id
        if self.raw_profile is not None:
            payload["raw_profile"] = self.raw_profile
        if self.obtained_at:
            payload["obtained_at"] = self.obtained_at.isoformat()
        if self.expires_at:
            payload["expires_at"] = self.expires_at.isoformat()
        return payload

    def to_config(self) -> Dict[str, Any]:
        config = dict(self.extras)
        config["access_token"] = self.access_token
        if self.extended_token:
            config["extended_token"] = self.extended_token
        if self.broker_user_id:
            config["broker_user_id"] = self.broker_user_id
        if self.raw_profile:
            config["raw_profile"] = self.raw_profile
        return config


class BaseTokenStore:
    def get_tokens(
        self,
        broker_name: str,
        *,
        connection_id: Optional[int] = None,
        broker_user_id: Optional[str] = None,
    ) -> Optional[TokenBundle]:
        raise NotImplementedError

    def store_tokens(
        self,
        broker_name: str,
        tokens: Any,
        *,
        connection_id: Optional[int] = None,
        user_id: Optional[int] = None,
        broker_user_id: Optional[str] = None,
    ) -> None:
        raise NotImplementedError

    def clear_tokens(
        self,
        broker_name: str,
        *,
        connection_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> bool:
        """Clear stored tokens without deleting the connection row."""
        raise NotImplementedError

    def disconnect(
        self,
        broker_name: str,
        *,
        connection_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> bool:
        raise NotImplementedError


class DbTokenStore(BaseTokenStore):
    def __init__(self, session_factory=SessionLocal) -> None:
        self._session_factory = session_factory
        self._encryptor = get_encryptor()

    def get_tokens(
        self,
        broker_name: str,
        *,
        connection_id: Optional[int] = None,
        broker_user_id: Optional[str] = None,
    ) -> Optional[TokenBundle]:
        if connection_id is None:
            raise ValueError("connection_id required for DB token store")
        with self._session_factory() as session:
            connection = session.get(models.BrokerConnection, connection_id)
            if not connection or connection.broker_name != broker_name:
                return None
            if not connection.encrypted_tokens:
                return None
            return TokenBundle.from_obj(
                self._encryptor.decrypt_dict(connection.encrypted_tokens)
            )

    def store_tokens(
        self,
        broker_name: str,
        tokens: Any,
        *,
        connection_id: Optional[int] = None,
        user_id: Optional[int] = None,
        broker_user_id: Optional[str] = None,
    ) -> None:
        bundle = TokenBundle.from_obj(tokens)
        payload = bundle.to_payload()
        if broker_user_id and not bundle.broker_user_id:
            payload["broker_user_id"] = broker_user_id
        encrypted = self._encryptor.encrypt_dict(payload)

        with self._session_factory() as session:
            if connection_id is None:
                if user_id is None:
                    raise ValueError(
                        "user_id required when creating new broker connection"
                    )

                new_broker_user_id = payload.get("broker_user_id")
                query = session.query(models.BrokerConnection).filter(
                    models.BrokerConnection.user_id == user_id,
                    models.BrokerConnection.broker_name == broker_name,
                )
                connection = None
                if new_broker_user_id:
                    connection = (
                        query.filter(
                            models.BrokerConnection.broker_user_id == new_broker_user_id
                        )
                        .order_by(models.BrokerConnection.id.desc())
                        .first()
                    )
                if connection is None:
                    # Reuse the broker's existing connection rather than adding a
                    # second row for the same user and broker.
                    connection = query.order_by(
                        models.BrokerConnection.encrypted_tokens.is_(None).asc(),
                        models.BrokerConnection.id.desc(),
                    ).first()
                if connection is None:
                    connection = models.BrokerConnection(
                        user_id=user_id,
                        broker_name=broker_name,
                        metadata_json=json.dumps({}),
                    )
                    session.add(connection)
            else:
                connection = session.get(models.BrokerConnection, connection_id)
                if not connection:
                    raise ValueError("Broker connection not found")

            new_broker_user_id = payload.get("broker_user_id")
            if new_broker_user_id:
                # Clear conflicting identities and flush before assigning this
                # one; SQLAlchemy would otherwise UPDATE before any DELETE.
                release_broker_identity(
                    session, connection=connection, broker_user_id=new_broker_user_id
                )
                connection.broker_user_id = new_broker_user_id
            connection.encrypted_tokens = encrypted
            connection.token_updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(connection)

    def clear_tokens(
        self,
        broker_name: str,
        *,
        connection_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> bool:
        """Clear stored tokens without deleting the connection row.

        Used when a broker reports definitive auth failure so stale tokens are not
        reused and reconnect flows can store fresh tokens.
        """
        broker_name = (broker_name or "").lower()
        with self._session_factory() as session:
            if connection_id is not None:
                connection = session.get(models.BrokerConnection, connection_id)
                if connection and connection.broker_name == broker_name:
                    if connection.encrypted_tokens is None and connection.token_updated_at is None:
                        return False
                    connection.encrypted_tokens = None
                    connection.token_updated_at = None
                    session.commit()
                    return True
                return False

            if user_id is not None:
                rows = (
                    session.query(models.BrokerConnection)
                    .filter(
                        models.BrokerConnection.user_id == user_id,
                        models.BrokerConnection.broker_name == broker_name,
                    )
                    .all()
                )
                changed = False
                for row in rows:
                    if row.encrypted_tokens is not None or row.token_updated_at is not None:
                        row.encrypted_tokens = None
                        row.token_updated_at = None
                        changed = True
                if changed:
                    session.commit()
                return changed

            raise ValueError("Either connection_id or user_id required")

    def disconnect(
        self,
        broker_name: str,
        *,
        connection_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> bool:
        with self._session_factory() as session:
            if connection_id is not None:
                connection = session.get(models.BrokerConnection, connection_id)
                if connection and connection.broker_name == broker_name:
                    session.delete(connection)
                    session.commit()
                    return True
                return False

            if user_id is not None:
                deleted = (
                    session.query(models.BrokerConnection)
                    .filter(
                        models.BrokerConnection.user_id == user_id,
                        models.BrokerConnection.broker_name == broker_name,
                    )
                    .delete()
                )
                session.commit()
                return deleted > 0

            raise ValueError("Either connection_id or user_id required")
