"""Ephemeral OAuth state tracking."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Dict


@dataclass
class OAuthState:
    token: str
    tenant_id: int
    user_id: int
    connection_id: int
    expires_at: datetime


class OAuthStateStore:
    def __init__(self, ttl_seconds: int = 300) -> None:
        self._ttl = ttl_seconds
        self._states: Dict[str, OAuthState] = {}
        self._lock = Lock()

    def issue(self, *, tenant_id: int, user_id: int, connection_id: int) -> str:
        token = secrets.token_urlsafe(16)
        state = OAuthState(
            token=token,
            tenant_id=tenant_id,
            user_id=user_id,
            connection_id=connection_id,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=self._ttl),
        )
        with self._lock:
            self._states[token] = state
        return token

    def consume(self, token: str) -> OAuthState:
        with self._lock:
            state = self._states.pop(token, None)
        if not state:
            raise ValueError("Invalid OAuth state token")
        if state.expires_at < datetime.now(timezone.utc):
            raise ValueError("Expired OAuth state token")
        return state


_oauth_state_store = OAuthStateStore()


def get_oauth_state_store() -> OAuthStateStore:
    return _oauth_state_store
