"""Ephemeral store for confirmation tokens."""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Dict


def _hash_payload(payload) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(serialized).hexdigest()


@dataclass
class ConfirmEntry:
    session_id: str
    user_id: int | None
    payload_hash: str
    expires_at: datetime


class ConfirmTokenStore:
    def __init__(self) -> None:
        self._entries: Dict[str, ConfirmEntry] = {}
        self._lock = Lock()

    def issue(self, *, session_id: str, user_id: int | None, payload) -> Dict[str, str]:
        payload_hash = _hash_payload(payload)
        token = secrets.token_urlsafe(24)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=60)
        entry = ConfirmEntry(session_id=session_id, user_id=user_id, payload_hash=payload_hash, expires_at=expires_at)
        with self._lock:
            self._entries[token] = entry
        return {"token": token, "expires_at": expires_at.isoformat()}

    def verify(self, *, token: str, session_id: str, user_id: int | None, payload) -> None:
        payload_hash = _hash_payload(payload)
        with self._lock:
            entry = self._entries.get(token)
            if not entry:
                raise ValueError("Invalid confirmation token")
            if entry.expires_at < datetime.now(timezone.utc):
                del self._entries[token]
                raise ValueError("Confirmation token expired")
            if entry.session_id != session_id or entry.user_id != user_id:
                raise ValueError("Confirmation token does not match session")
            if entry.payload_hash != payload_hash:
                raise ValueError("Payload mismatch for confirmation token")
            del self._entries[token]


_confirm_store = ConfirmTokenStore()


def get_confirm_store() -> ConfirmTokenStore:
    return _confirm_store
