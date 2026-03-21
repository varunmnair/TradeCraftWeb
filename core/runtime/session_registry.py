"""In-memory registry that keeps per-session contexts."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import TYPE_CHECKING, Any, Dict, Optional
from uuid import uuid4

from brokers.broker_factory import BrokerFactory
from core.auth.context import UserContext
from core.session import SessionCache
from core.session_manager import SessionManager
from core.session_tokens import TokenBundle
from db import models
from db.database import SessionLocal

logger = logging.getLogger("tradecraftx.session")

if TYPE_CHECKING:
    from brokers.base_broker import BaseBroker


@dataclass
class SessionContext:
    session_id: str
    broker_user_id: str
    broker_name: str
    created_at: datetime
    expires_at: Optional[datetime]
    broker: "BaseBroker"
    session_cache: SessionCache
    session_manager: SessionManager
    user_record_id: Optional[int] = None
    trading_broker_connection_id: Optional[int] = None
    market_data_connection_id: Optional[int] = None

    def refresh_all(self) -> None:
        self.session_cache.refresh_all_caches()


class SessionRegistry:
    """Tracks active sessions and evicts them after TTL."""

    def __init__(
        self,
        *,
        session_cache_cls=SessionCache,
        session_manager_cls=SessionManager,
        broker_factory=BrokerFactory,
        session_factory=SessionLocal,
        session_manager: SessionManager | None = None,
    ) -> None:
        self._records: Dict[str, SessionContext] = {}
        self._lock = Lock()
        self._session_cache_cls = session_cache_cls
        self._session_manager_cls = session_manager_cls
        self._broker_factory = broker_factory
        self._session_factory = session_factory
        self._session_manager = session_manager or session_manager_cls()

    def create_session(
        self,
        *,
        broker_user_id: Optional[str] = None,
        broker_name: Optional[str] = None,
        broker_config: Optional[Dict[str, Any]] = None,
        broker_connection_id: Optional[int] = None,
        market_data_connection_id: Optional[int] = None,
        ttl_minutes: int = 60,
    ) -> SessionContext:
        user_record_id = None
        if broker_connection_id is not None:
            broker_user_id, broker_name, broker_config, user_record_id = (
                self._load_broker_connection(broker_connection_id)
            )

        if not broker_user_id or not broker_name or broker_config is None:
            raise ValueError(
                "broker_user_id, broker_name, and broker_config are required to start a session"
            )

        if broker_name == "zerodha" and market_data_connection_id is None:
            market_data_connection_id = self._find_active_upstox_connection(
                user_record_id
            )
            if market_data_connection_id is not None:
                self._validate_upstox_connection(
                    market_data_connection_id, user_record_id
                )
        elif broker_name == "upstox" and market_data_connection_id is None:
            market_data_connection_id = broker_connection_id

        session_manager = self._session_manager
        broker = self._broker_factory.get_broker(
            broker_name, broker_user_id, broker_config
        )
        if hasattr(broker, "set_session_context"):
            broker.set_session_context(
                session_manager=session_manager,
                connection_id=broker_connection_id,
            )

        if hasattr(broker, "login"):
            broker.login()

        session_cache = self._session_cache_cls(
            session_manager=session_manager,
            market_data_connection_id=market_data_connection_id,
            user_id=user_record_id,
        )
        session_cache.broker = broker  # type: ignore[attr-defined]

        record_id = str(uuid4())
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=ttl_minutes)
        context = SessionContext(
            session_id=record_id,
            broker_user_id=broker_user_id,
            broker_name=broker_name,
            created_at=now,
            expires_at=expires_at,
            broker=broker,
            session_cache=session_cache,
            session_manager=session_manager,
            user_record_id=user_record_id,
            trading_broker_connection_id=broker_connection_id,
            market_data_connection_id=market_data_connection_id,
        )
        with self._lock:
            self._records[record_id] = context
        return context

    def _find_active_upstox_connection(self, user_record_id: int) -> Optional[int]:
        """Find an active Upstox connection for the given user."""
        with self._session_factory() as db:
            from sqlalchemy import and_

            connections = (
                db.query(models.BrokerConnection)
                .filter(
                    and_(
                        models.BrokerConnection.user_id == user_record_id,
                        models.BrokerConnection.broker_name == "upstox",
                    )
                )
                .all()
            )
            for conn in connections:
                bundle = self._session_manager.get_token_bundle(
                    "upstox", connection_id=conn.id
                )
                if bundle:
                    return conn.id
        return None

    def _validate_upstox_connection(
        self, connection_id: int, user_record_id: int
    ) -> None:
        """Validate that the given connection is a valid Upstox connection."""
        with self._session_factory() as db:
            connection = db.get(models.BrokerConnection, connection_id)
            if not connection:
                raise ValueError("Market data connection not found")
            if connection.broker_name != "upstox":
                raise ValueError("Market data provider must be Upstox")
            if connection.user_id != user_record_id:
                raise ValueError("Market data connection belongs to another user")
            bundle = self._session_manager.get_token_bundle(
                "upstox", connection_id=connection_id
            )
            if not bundle:
                raise ValueError("Market data connection has no valid token")

    def _load_broker_connection(
        self, connection_id: int
    ) -> tuple[str, str, Dict[str, Any], Optional[int]]:
        with self._session_factory() as db:
            connection = db.get(models.BrokerConnection, connection_id)
            if not connection:
                raise ValueError("Broker connection not found")
            bundle = self._session_manager.get_token_bundle(
                connection.broker_name,
                connection_id=connection_id,
            )
            if not bundle:
                raise ValueError("Token bundle missing for broker connection")
            metadata = (
                connection.metadata_dict()
                if hasattr(connection, "metadata_dict")
                else {}
            )
            config = self._build_broker_config(bundle, metadata, connection_id)
            broker_name = connection.broker_name
            broker_user_id = (
                bundle.broker_user_id
                or connection.broker_user_id
                or metadata.get("broker_user_id")
                or str(connection.user_id)
            )
            return broker_user_id, broker_name, config, connection.user_id

    @staticmethod
    def _build_broker_config(
        bundle: TokenBundle, metadata: Dict[str, Any], connection_id: int
    ) -> Dict[str, Any]:
        config = {**metadata, **bundle.to_config()}
        config.setdefault("broker_connection_id", connection_id)
        return config

    def require_access(self, session_id: str, user: UserContext) -> SessionContext:
        context = self.get_session(session_id)
        if not context:
            raise ValueError("Session not found or expired")
        if (
            not user.is_dev
            and context.user_record_id
            and user.user_id != context.user_record_id
        ):
            raise ValueError("Session owned by another user")
        return context

    def get_session(self, session_id: str) -> Optional[SessionContext]:
        with self._lock:
            context = self._records.get(session_id)
            if not context:
                return None
            if context.expires_at and context.expires_at < datetime.now(timezone.utc):
                del self._records[session_id]
                return None
            
            # Load order history from DB if not already loaded
            if context.session_cache and not context.session_cache.get_order_history_status()["available"]:
                self._load_session_order_history(context)
            
            return context

    def _load_session_order_history(self, context: "SessionContext") -> None:
        """Load order history from database into session cache."""
        try:
            from api.routes.holdings_v2 import _load_trades_from_db
            
            trades = _load_trades_from_db(context.session_id)
            if trades:
                source = trades[0].get("source", "unknown") if trades else None
                context.session_cache.set_order_history(trades, source=source)
                logger.info(f"Loaded {len(trades)} trades from DB for session {context.session_id}")
        except Exception as e:
            logger.warning(f"Failed to load order history from DB: {e}")

    def refresh_session(self, session_id: str) -> Optional[SessionContext]:
        context = self.get_session(session_id)
        if context:
            context.refresh_all()
        return context

    def evict(self, session_id: str) -> None:
        """Evict a session and clear all session-scoped data."""
        context = self._records.get(session_id)
        if context:
            # Clear session-scoped holdings and order history
            self._clear_session_data(context)
        
        with self._lock:
            self._records.pop(session_id, None)

    def evict_by_connection(self, broker_connection_id: int) -> int:
        """Evict all sessions that use the given broker connection."""
        with self._lock:
            to_evict = [
                sid
                for sid, ctx in self._records.items()
                if ctx.trading_broker_connection_id == broker_connection_id
                or ctx.market_data_connection_id == broker_connection_id
            ]
            for sid in to_evict:
                ctx = self._records.get(sid)
                if ctx:
                    self._clear_session_data(ctx)
                del self._records[sid]
            return len(to_evict)

    def _clear_session_data(self, context: "SessionContext") -> None:
        """Clear all session-scoped data including holdings and order history."""
        try:
            # Clear order history from session cache
            if hasattr(context, 'session_cache') and context.session_cache:
                context.session_cache.clear_order_history()
            
            # Clear holdings (set to empty list)
            if hasattr(context, 'session_cache') and context.session_cache:
                context.session_cache.holdings = []
            
            logging.info(f"Cleared session data for session: {context.session_id}")
        except Exception as e:
            logging.warning(f"Failed to clear session data: {e}")

    def active_sessions(self) -> int:
        with self._lock:
            return len(self._records)
