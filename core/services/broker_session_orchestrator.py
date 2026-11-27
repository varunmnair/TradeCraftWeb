"""Lightweight orchestration for broker connection -> trading session readiness.

This service deliberately composes the existing BrokerConnectionService,
SessionRegistry and SessionService. It does not replace or merge them.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from core.auth.active_connection_store import (
    ActiveConnectionStore,
    get_active_connection_store,
)
from core.auth.context import UserContext
from core.runtime.session_registry import SessionRegistry
from core.services.broker_connection_service import BrokerConnectionService
from core.services.session_service import SessionService
from core.session_manager import SessionManager

LOGGER = logging.getLogger("tradecraftx.session_orchestrator")


class SessionReadiness(str, Enum):
    CONNECTED = "CONNECTED"
    INITIALIZING = "INITIALIZING"
    LOADING = "LOADING"
    READY = "READY"
    ERROR = "ERROR"


@dataclass
class BrokerAccount:
    connection_id: int
    broker_name: str
    broker_user_id: Optional[str] = None
    token_status: str = "missing"
    expires_at: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "connection_id": self.connection_id,
            "broker_name": self.broker_name,
            "broker_user_id": self.broker_user_id,
            "token_status": self.token_status,
            "expires_at": self.expires_at,
        }


@dataclass
class OrchestrationResult:
    status: SessionReadiness
    broker_connected: bool = False
    requires_selection: bool = False
    broker_name: Optional[str] = None
    connection_id: Optional[int] = None
    broker_user_id: Optional[str] = None
    session_id: Optional[str] = None
    session: Optional[dict[str, Any]] = None
    candidates: list[dict[str, Any]] = field(default_factory=list)
    message: Optional[str] = None
    data_status: str = "unavailable"


class BrokerSessionOrchestrator:
    """Resolve, reuse or initialize a device-scoped trading session."""

    def __init__(
        self,
        *,
        connection_service: BrokerConnectionService,
        session_service: SessionService,
        session_registry: SessionRegistry,
        session_manager: SessionManager,
        active_store: Optional[ActiveConnectionStore] = None,
    ) -> None:
        self._connections = connection_service
        self._sessions = session_service
        self._registry = session_registry
        self._session_manager = session_manager
        self._active_store = active_store or get_active_connection_store()
        self._locks: dict[tuple[int, str, int], threading.Lock] = {}
        self._locks_guard = threading.Lock()

    @staticmethod
    def _token_state(bundle: Any) -> tuple[str, Optional[str]]:
        if bundle is None or not getattr(bundle, "access_token", None):
            return "missing", None
        expires_at = getattr(bundle, "expires_at", None)
        if expires_at is None:
            return "valid", None
        try:
            expires_text = str(expires_at).replace("Z", "+00:00")
            expires = datetime.fromisoformat(expires_text)
        except (TypeError, ValueError):
            return "valid", str(expires_at)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        status = "expired" if expires <= datetime.now(timezone.utc) else "valid"
        return status, expires.isoformat()

    def available_accounts(
        self, user_id: int, broker_name: Optional[str] = None
    ) -> list[BrokerAccount]:
        """List broker connections whose stored broker token is usable."""
        wanted = broker_name.lower() if broker_name else None
        accounts: list[BrokerAccount] = []
        for connection in self._connections.list_connections(user_id=user_id):
            if wanted and connection.broker_name.lower() != wanted:
                continue
            bundle = self._session_manager.get_token_bundle(
                connection.broker_name, connection_id=connection.id
            )
            token_status, expires_at = self._token_state(bundle)
            if token_status != "valid":
                continue
            broker_user_id = (
                getattr(bundle, "broker_user_id", None)
                or getattr(connection, "broker_user_id", None)
                or str(connection.user_id)
            )
            accounts.append(
                BrokerAccount(
                    connection_id=connection.id,
                    broker_name=connection.broker_name,
                    broker_user_id=broker_user_id,
                    token_status=token_status,
                    expires_at=expires_at,
                )
            )
        return accounts

    def _lock_for(self, user_id: int, device_id: str, connection_id: int) -> threading.Lock:
        key = (user_id, device_id, connection_id)
        with self._locks_guard:
            return self._locks.setdefault(key, threading.Lock())

    def _selection_required(
        self, accounts: list[BrokerAccount], broker_name: Optional[str]
    ) -> str | None:
        if len(accounts) <= 1:
            return None
        brokers = {account.broker_name.lower() for account in accounts}
        if len(brokers) > 1:
            return "Both Zerodha and Upstox are connected. Select a broker to continue."
        label = accounts[0].broker_name.capitalize()
        return f"Multiple accounts are available for {label}. Select one to continue."

    def _session_to_result(
        self,
        session: dict[str, Any],
        *,
        connection_id: int,
        broker_name: str,
        broker_user_id: Optional[str],
        candidates: list[dict[str, Any]],
        message: Optional[str] = None,
        data_status: str = "fresh",
    ) -> OrchestrationResult:
        return OrchestrationResult(
            status=SessionReadiness.READY,
            broker_connected=True,
            broker_name=broker_name,
            connection_id=connection_id,
            broker_user_id=session.get("broker_user_id") or broker_user_id,
            session_id=session.get("session_id"),
            session=session,
            candidates=candidates,
            message=message,
            data_status=data_status,
        )

    def _existing_device_session(self, user_id: int, device_id: str):
        return self._registry.find_session_for_user(user_id, device_id)

    def _recover_existing_session(
        self, user_id: int, device_id: str, candidates: list[dict[str, Any]]
    ) -> OrchestrationResult | None:
        existing = self._existing_device_session(user_id, device_id)
        if not existing:
            return None
        try:
            session = self._sessions.refresh_caches(existing.session_id)
        except Exception:
            LOGGER.exception(
                "Session recovery failed for session_id=%s", existing.session_id
            )
            return None
        self._active_store.set_active_connection(
            user_id, existing.trading_broker_connection_id, device_id
        )
        return self._session_to_result(
            session,
            connection_id=existing.trading_broker_connection_id,
            broker_name=existing.broker_name,
            broker_user_id=existing.broker_user_id,
            candidates=candidates,
        )

    def orchestrate(
        self,
        user: UserContext,
        *,
        broker_name: Optional[str] = None,
        broker_connection_id: Optional[int] = None,
        warm_start: bool = True,
        refresh_data: bool = False,
    ) -> OrchestrationResult:
        """Resolve, reuse or initialize a device-scoped trading session.

        Explicit activation: broker_connection_id or broker_name is provided.
        Recovery/no-op: no explicit target - reuse existing device session or
        the device's explicitly-selected active connection; never auto-pick a
        new broker on login.
        """
        if not user.user_id:
            return OrchestrationResult(
                status=SessionReadiness.ERROR,
                message="User context is missing. Sign in again.",
            )

        device_id = user.device_id or "default-device"
        explicit_target = broker_connection_id is not None or broker_name is not None
        accounts = self.available_accounts(user.user_id, broker_name)
        candidate_dicts = [account.as_dict() for account in accounts]

        if broker_connection_id is not None:
            accounts = [a for a in accounts if a.connection_id == broker_connection_id]
            if not accounts:
                existing = self._recover_existing_session(
                    user.user_id, device_id, candidate_dicts
                )
                if existing:
                    existing.message = (
                        "The selected broker connection is no longer valid. "
                        "Your current session is still active."
                    )
                    return existing
                return OrchestrationResult(
                    status=SessionReadiness.ERROR,
                    candidates=candidate_dicts,
                    message="The selected broker connection is no longer valid. Connect the broker again.",
                )

        if not explicit_target:
            # Recovery only: keep an already-active device session, or restore the
            # device's explicitly selected active connection. Never auto-select.
            existing = self._existing_device_session(user.user_id, device_id)
            if existing:
                recovered = self._recover_existing_session(
                    user.user_id, device_id, candidate_dicts
                )
                if recovered:
                    return recovered
                return OrchestrationResult(
                    status=SessionReadiness.ERROR,
                    broker_connected=True,
                    broker_name=existing.broker_name,
                    connection_id=existing.trading_broker_connection_id,
                    broker_user_id=existing.broker_user_id,
                    session_id=existing.session_id,
                    candidates=candidate_dicts,
                    message="Session recovery failed. Retry to continue.",
                )

            active_connection_id = self._active_store.get_active_connection(
                user.user_id, device_id
            )
            if active_connection_id is not None:
                active_accounts = [
                    a for a in self.available_accounts(user.user_id)
                    if a.connection_id == active_connection_id
                ]
                if active_accounts:
                    return self._activate_account(
                        user.user_id,
                        device_id,
                        active_accounts[0],
                        warm_start=warm_start,
                        candidate_dicts=candidate_dicts,
                    )
                self._active_store.clear_active_connection(user.user_id, device_id)

            if not candidate_dicts:
                return OrchestrationResult(
                    status=SessionReadiness.ERROR,
                    candidates=candidate_dicts,
                    message="No broker is connected. Connect a broker to start a trading session.",
                )
            return OrchestrationResult(
                status=SessionReadiness.CONNECTED,
                broker_connected=True,
                requires_selection=False,
                candidates=candidate_dicts,
                message="Select a broker to start a trading session.",
            )

        if not accounts:
            existing = self._recover_existing_session(
                user.user_id, device_id, candidate_dicts
            )
            if existing:
                existing.message = (
                    "Unable to activate the selected broker. Your current session is still active."
                )
                return existing
            return OrchestrationResult(
                status=SessionReadiness.ERROR,
                candidates=candidate_dicts,
                message="No broker is connected. Connect a broker to start a trading session.",
            )

        selection_message = self._selection_required(accounts, broker_name)
        if selection_message:
            return OrchestrationResult(
                status=SessionReadiness.CONNECTED,
                broker_connected=True,
                requires_selection=True,
                candidates=[account.as_dict() for account in accounts],
                message=selection_message,
            )

        return self._activate_account(
            user.user_id,
            device_id,
            accounts[0],
            warm_start=warm_start,
            candidate_dicts=candidate_dicts,
        )

    def _activate_account(
        self,
        user_id: int,
        device_id: str,
        account: BrokerAccount,
        *,
        warm_start: bool,
        candidate_dicts: list[dict[str, Any]],
    ) -> OrchestrationResult:
        result = OrchestrationResult(
            status=SessionReadiness.CONNECTED,
            broker_connected=True,
            broker_name=account.broker_name,
            connection_id=account.connection_id,
            broker_user_id=account.broker_user_id,
            candidates=[account.as_dict()],
        )
        lock = self._lock_for(user_id, device_id, account.connection_id)
        with lock:
            existing = self._registry.find_session_for_connection(
                user_id, device_id, account.connection_id
            )
            if existing:
                try:
                    session = self._sessions.refresh_caches(existing.session_id)
                except Exception:
                    LOGGER.exception(
                        "Session refresh failed for session_id=%s connection_id=%d",
                        existing.session_id,
                        account.connection_id,
                    )
                    fallback = self._recover_existing_session(
                        user_id, device_id, candidate_dicts
                    )
                    if fallback and fallback.session_id != existing.session_id:
                        fallback.message = (
                            "Session recovery failed. Your current session is still active."
                        )
                        return fallback
                    result.status = SessionReadiness.ERROR
                    result.message = "Broker connected. Session initialization failed."
                    return result
                self._active_store.set_active_connection(
                    user_id, account.connection_id, device_id
                )
                self._registry.evict_other_sessions_for_device(
                    user_id, device_id, existing.session_id
                )
                result.status = SessionReadiness.READY
                result.session_id = session.get("session_id")
                result.broker_user_id = (
                    session.get("broker_user_id") or account.broker_user_id
                )
                result.session = session
                return result

            try:
                session = self._sessions.start_session(
                    broker_connection_id=account.connection_id,
                    warm_start=warm_start,
                    device_id=device_id,
                )
            except Exception:
                LOGGER.exception(
                    "Session initialization failed for user_id=%d connection_id=%d",
                    user_id,
                    account.connection_id,
                )
                fallback = self._fallback_after_switch_failure(
                    user_id, device_id, candidate_dicts, account.connection_id
                )
                if fallback:
                    fallback.message = (
                        f"Unable to activate {account.broker_name.capitalize()}. "
                        "Your current session is still active."
                    )
                    return fallback
                result.status = SessionReadiness.ERROR
                result.message = "Broker connected. Session initialization failed."
                return result

            if session.get("warm_start") is False:
                fallback = self._fallback_after_switch_failure(
                    user_id, device_id, candidate_dicts, account.connection_id
                )
                if fallback:
                    fallback.message = (
                        f"Unable to activate {account.broker_name.capitalize()}. "
                        "Your current session is still active."
                    )
                    return fallback
                result.status = SessionReadiness.ERROR
                result.message = "Broker connected. Session initialization failed."
                result.session_id = session.get("session_id")
                result.session = session
                return result

            self._active_store.set_active_connection(
                user_id, account.connection_id, device_id
            )
            self._registry.evict_other_sessions_for_device(
                user_id, device_id, session.get("session_id")
            )
            result.status = SessionReadiness.READY
            result.session_id = session.get("session_id")
            result.broker_user_id = (
                session.get("broker_user_id") or account.broker_user_id
            )
            result.session = session
            result.data_status = "fresh"
            return result

    def _fallback_after_switch_failure(
        self,
        user_id: int,
        device_id: str,
        candidate_dicts: list[dict[str, Any]],
        failed_connection_id: int,
    ) -> OrchestrationResult | None:
        existing = self._existing_device_session(user_id, device_id)
        if not existing:
            return None
        if existing.trading_broker_connection_id == failed_connection_id:
            return None
        return self._recover_existing_session(user_id, device_id, candidate_dicts)
