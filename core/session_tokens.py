"""Token storage abstractions for CLI vs SaaS."""

from __future__ import annotations

import json
import pickle
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from core.security.encryption import get_encryptor
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

                existing_connections = (
                    session.query(models.BrokerConnection)
                    .filter(
                        models.BrokerConnection.user_id == user_id,
                        models.BrokerConnection.broker_name == broker_name,
                    )
                    .all()
                )
                for old_conn in existing_connections:
                    session.delete(old_conn)

                new_broker_user_id = payload.get("broker_user_id")
                connection = models.BrokerConnection(
                    user_id=user_id,
                    broker_name=broker_name,
                    encrypted_tokens=encrypted,
                    metadata_json=json.dumps({}),
                    broker_user_id=new_broker_user_id,
                    token_updated_at=datetime.now(timezone.utc),
                )
                session.add(connection)
                session.commit()
                session.refresh(connection)
                return

            connection = session.get(models.BrokerConnection, connection_id)
            if not connection:
                raise ValueError("Broker connection not found")

            new_broker_user_id = payload.get("broker_user_id")
            if new_broker_user_id and new_broker_user_id != connection.broker_user_id:
                existing = (
                    session.query(models.BrokerConnection)
                    .filter(
                        models.BrokerConnection.user_id == connection.user_id,
                        models.BrokerConnection.broker_name == connection.broker_name,
                        models.BrokerConnection.broker_user_id == new_broker_user_id,
                        models.BrokerConnection.id != connection_id,
                    )
                    .first()
                )
                if existing:
                    session.delete(existing)

            connection.encrypted_tokens = encrypted
            connection.broker_user_id = new_broker_user_id or connection.broker_user_id
            connection.token_updated_at = datetime.now(timezone.utc)
            session.commit()

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
