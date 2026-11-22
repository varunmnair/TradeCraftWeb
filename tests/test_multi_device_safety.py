"""Stage 5B: device-scoped broker/session context and non-destructive reconnect."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.auth.active_connection_store import ActiveConnectionStore
from core.auth.context import UserContext
from core.security.passwords import hash_password
from core.services.auth_service import AuthService
from core.runtime.session_registry import SessionRegistry
from core.services.broker_connection_service import BrokerConnectionService
from core.session_tokens import DbTokenStore
from db import models
from db.database import Base


class DummyBroker:
    broker_name = "dummy"

    def __init__(self, broker_user_id: str) -> None:
        self.broker_user_id = broker_user_id

    def get_holdings(self):
        return []

    def load_entry_levels(self, _path):
        return []

    def get_gtt_orders(self):
        return []


class DummyBrokerFactory:
    def get_broker(self, broker_name, broker_user_id, config):
        return DummyBroker(broker_user_id)


def _user(device_id: str | None) -> UserContext:
    return UserContext(user_id=7, email="user@example.com", role="user", device_id=device_id)


def test_active_connection_is_scoped_per_device():
    store = ActiveConnectionStore()
    store.set_active_connection(1, 100, "laptop")
    store.set_active_connection(1, 200, "mobile")

    assert store.get_active_connection(1, "laptop") == 100
    assert store.get_active_connection(1, "mobile") == 200
    assert store.get_active_connection(2, "laptop") is None

    store.clear_active_connection(1, "mobile")
    assert store.get_active_connection(1, "laptop") == 100
    assert store.get_active_connection(1, "mobile") is None


def test_multiple_sessions_per_user_and_device_isolation():
    registry = SessionRegistry(broker_factory=DummyBrokerFactory())
    laptop = registry.create_session(
        broker_user_id="alice", broker_name="dummy", broker_config={}, device_id="laptop"
    )
    mobile = registry.create_session(
        broker_user_id="alice", broker_name="dummy", broker_config={}, device_id="mobile"
    )
    for context in (laptop, mobile):
        context.user_record_id = 7

    assert laptop.session_id != mobile.session_id
    assert registry.require_access(laptop.session_id, _user("laptop")) is laptop
    assert registry.require_access(mobile.session_id, _user("mobile")) is mobile

    with pytest.raises(ValueError, match="another device"):
        registry.require_access(laptop.session_id, _user("mobile"))

    # Legacy callers without a device id keep working.
    assert registry.require_access(laptop.session_id, _user(None)) is laptop

    assert registry.evict_by_device(7, "laptop") == 1
    assert registry.get_session(laptop.session_id) is None
    assert registry.get_session(mobile.session_id) is not None


def test_broker_reconnection_does_not_delete_other_connections():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        session.add(models.User(email="user@example.com"))
        session.commit()

    service = BrokerConnectionService(session_factory=factory)
    first = service.ensure_connection(user_id=1, broker_name="upstox")
    second = service.ensure_connection(user_id=1, broker_name="upstox")

    assert first.id != second.id
    assert len(service.list_connections(user_id=1)) == 2


def test_store_tokens_reuses_connection_without_deleting_others():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        session.add(models.User(email="user@example.com"))
        session.commit()

    now = datetime.now(timezone.utc)
    tokens = {
        "access_token": "ACCESS123",
        "extended_token": "EXT456",
        "broker_user_id": "BROKERID",
        "raw_profile": {"name": "User"},
        "obtained_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
    }
    store = DbTokenStore(session_factory=factory)
    store.store_tokens("upstox", tokens, user_id=1)
    store.store_tokens("upstox", tokens, user_id=1)

    connections = store.list_connections(user_id=1) if hasattr(store, "list_connections") else None
    with factory() as session:
        count = (
            session.query(models.BrokerConnection)
            .filter(models.BrokerConnection.user_id == 1)
            .count()
        )
    assert count == 1
    assert connections is None or len(connections) == 1


def test_session_expiration_removes_stale_session():
    registry = SessionRegistry(broker_factory=DummyBrokerFactory())
    context = registry.create_session(
        broker_user_id="alice", broker_name="dummy", broker_config={}, device_id="mobile", ttl_minutes=-1
    )
    assert registry.get_session(context.session_id) is None


def test_refresh_token_rotation_prevents_reuse():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        user = models.User(email="refresh@example.com", role="user")
        session.add(user)
        session.flush()
        session.add(
            models.UserIdentity(
                user_id=user.id,
                provider="password",
                password_hash=hash_password("strong-password"),
            )
        )
        session.commit()

    service = AuthService(session_factory=factory)
    original = service.login(email="refresh@example.com", password="strong-password")
    rotated = service.refresh(original.refresh_token)

    assert rotated.refresh_token != original.refresh_token
    with pytest.raises(ValueError, match="revoked"):
        service.refresh(original.refresh_token)
