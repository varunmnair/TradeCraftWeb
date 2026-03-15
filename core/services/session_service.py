"""Session orchestration logic for the API runtime."""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.runtime.session_registry import SessionRegistry


class SessionService:
    """Creates, refreshes, and inspects sessions."""

    def __init__(self, *, registry: SessionRegistry) -> None:
        self._registry = registry

    def start_session(
        self,
        *,
        user_id: Optional[str] = None,
        broker_name: Optional[str] = None,
        broker_config: Optional[Dict[str, Any]] = None,
        broker_connection_id: Optional[int] = None,
        market_data_connection_id: Optional[int] = None,
        warm_start: bool = False,
    ) -> Dict[str, Any]:
        context = self._registry.create_session(
            user_id=user_id,
            broker_name=broker_name,
            broker_config=broker_config,
            broker_connection_id=broker_connection_id,
            market_data_connection_id=market_data_connection_id,
        )
        if warm_start:
            context.refresh_all()
        return self._serialize_context(context)

    def refresh_caches(self, session_id: str) -> Dict[str, Any]:
        context = self._registry.refresh_session(session_id)
        if not context:
            raise ValueError("Session not found or expired")
        return self._serialize_context(context)

    def get_session_info(self, session_id: str) -> Dict[str, Any]:
        context = self._registry.get_session(session_id)
        if not context:
            raise ValueError("Session not found or expired")
        return self._serialize_context(context)

    @staticmethod
    def _serialize_context(context) -> Dict[str, Any]:
        return {
            "session_id": context.session_id,
            "user_id": context.user_id,
            "broker": context.broker_name,
            "expires_at": context.expires_at.isoformat() if context.expires_at else None,
            "tenant_id": context.tenant_id,
        }
