"""In-memory store for active broker connections.

Connections are scoped by user *and device/session*. A laptop and a phone
signed in as the same user can therefore keep independent broker selections.
The default device keeps legacy callers working unchanged.
"""

from __future__ import annotations

from threading import Lock
from typing import Dict, Optional

DEFAULT_DEVICE_ID = "default-device"


class ActiveConnectionStore:
    """Thread-safe store mapping (user_id, device_id) -> broker_connection_id."""

    def __init__(self) -> None:
        self._store: Dict[tuple[int, str], int] = {}
        self._lock = Lock()

    @staticmethod
    def _key(user_id: int, device_id: Optional[str]) -> tuple[int, str]:
        return (user_id, device_id or DEFAULT_DEVICE_ID)

    def set_active_connection(
        self,
        user_id: int,
        connection_id: int,
        device_id: Optional[str] = None,
    ) -> None:
        with self._lock:
            self._store[self._key(user_id, device_id)] = connection_id

    def get_active_connection(
        self, user_id: int, device_id: Optional[str] = None
    ) -> Optional[int]:
        with self._lock:
            return self._store.get(self._key(user_id, device_id))

    def clear_active_connection(
        self, user_id: int, device_id: Optional[str] = None
    ) -> None:
        with self._lock:
            self._store.pop(self._key(user_id, device_id), None)

    def clear_all_for_user(self, user_id: int) -> int:
        """Clear every device selection for a user. Used by logout-all only."""
        with self._lock:
            keys = [key for key in self._store if key[0] == user_id]
            for key in keys:
                del self._store[key]
            return len(keys)


_active_connection_store = ActiveConnectionStore()


def get_active_connection_store() -> ActiveConnectionStore:
    return _active_connection_store
