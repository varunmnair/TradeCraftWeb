"""Service to manage broker OAuth state tokens."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from db import models
from db.database import SessionLocal


class BrokerAuthStateService:
    def __init__(self, session_factory=SessionLocal, ttl_seconds: int = 600) -> None:
        self._session_factory = session_factory
        self._ttl = ttl_seconds

    def create_state(
        self, *, user_id: int, connection_id: int, broker_name: str
    ) -> str:
        token = secrets.token_urlsafe(24)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self._ttl)
        with self._session_factory() as session:
            state = models.BrokerAuthState(
                user_id=user_id,
                connection_id=connection_id,
                broker_name=broker_name,
                state_token=token,
                expires_at=expires_at,
            )
            session.add(state)
            session.commit()
        return token

    def consume_state(self, token: str) -> models.BrokerAuthState:
        with self._session_factory() as session:
            state = (
                session.query(models.BrokerAuthState)
                .filter(models.BrokerAuthState.state_token == token)
                .one_or_none()
            )
            if not state:
                raise ValueError("Invalid or expired state token")
            expires_at = state.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < datetime.now(timezone.utc):
                session.delete(state)
                session.commit()
                raise ValueError("State token expired")
            session.delete(state)
            session.commit()
            return state

    def delete_states_for_connection(self, connection_id: int) -> None:
        with self._session_factory() as session:
            session.query(models.BrokerAuthState).filter(
                models.BrokerAuthState.connection_id == connection_id
            ).delete()
            session.commit()
