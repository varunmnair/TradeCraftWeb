"""In-memory store for active broker connections per user."""

from __future__ import annotations

from threading import Lock
from typing import Dict, Optional


class ActiveConnectionStore:
    """Thread-safe store mapping user_id -> active broker_connection_id."""

    def __init__(self) -> None:
        self._store: Dict[int, int] = {}
        self._lock = Lock()

    def set_active_connection(self, user_id: int, connection_id: int) -> None:
        with self._lock:
            self._store[user_id] = connection_id

    def get_active_connection(self, user_id: int) -> Optional[int]:
        with self._lock:
            return self._store.get(user_id)

    def clear_active_connection(self, user_id: int) -> None:
        with self._lock:
            self._store.pop(user_id, None)


_active_connection_store = ActiveConnectionStore()


def get_active_connection_store() -> ActiveConnectionStore:
    return _active_connection_store
