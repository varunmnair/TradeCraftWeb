"""Stage 5C: broker context validation, idempotency, and uncertain outcomes."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.auth.context import UserContext
from core.gtt_manage import GTTManager
from core.runtime.session_registry import SessionRegistry
from core.services.placement_guard import (
    PlacementConflictError,
    PlacementContextError,
    PlacementGuardService,
    classify_broker_error,
    resolve_idempotency_key,
    validate_placement_context,
)
from db import models
from db.database import Base


class DummyBroker:
    broker_name = "dummy"
    GTT_TYPE_SINGLE = "single"
    TRANSACTION_TYPE_BUY = "BUY"
    ORDER_TYPE_LIMIT = "LIMIT"
    PRODUCT_CNC = "CNC"

    def __init__(self, *, fail: BaseException | None = None) -> None:
        self.broker_user_id = "alice"
        self.fail = fail
        self.calls = 0

    def get_holdings(self):
        return []

    def load_entry_levels(self, _path):
        return []

    def get_gtt_orders(self):
        return []

    def place_gtt(self, **_kwargs):
        self.calls += 1
        if self.fail:
            raise self.fail
        return {"order_id": "GTT-1"}


class DummyBrokerFactory:
    def get_broker(self, broker_name, broker_user_id, config):
        return DummyBroker()


class DummySession:
    def __init__(self) -> None:
        self.refreshed = 0

    def get_entry_levels(self):
        return []

    def refresh_gtt_cache(self) -> None:
        self.refreshed += 1


@pytest.fixture
def placement_factory():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


def _context(connection_id: int = 42):
    return {
        "session_id": "session-1",
        "user_id": 7,
        "broker_name": "zerodha",
        "broker_connection_id": connection_id,
        "device_id": "mobile",
    }


def test_idempotency_claim_replays_completed_request(placement_factory):
    guard = PlacementGuardService(placement_factory)
    key, fingerprint = resolve_idempotency_key(
        user_id=7,
        session_id="session-1",
        device_id="mobile",
        payload={"symbols": ["ABC"]},
        explicit_key="attempt-1",
    )

    first = guard.claim(
        user_id=7,
        idempotency_key=key,
        request_hash_value=fingerprint,
        context=_context(),
    )
    guard.complete(
        user_id=7,
        idempotency_key=key,
        status="completed",
        result={"results": [{"symbol": "ABC", "status": "Success"}]},
    )
    second = guard.claim(
        user_id=7,
        idempotency_key=key,
        request_hash_value=fingerprint,
        context=_context(),
    )

    assert first["claimed"] is True
    assert second["claimed"] is False
    assert second["replayed"] is True
    assert "ABC" in second["record"]["result_json"]


def test_idempotency_key_reuse_with_different_request_is_rejected(placement_factory):
    guard = PlacementGuardService(placement_factory)
    guard.claim(
        user_id=7,
        idempotency_key="same-key",
        request_hash_value="hash-a",
        context=_context(),
    )

    with pytest.raises(PlacementConflictError, match="different order request"):
        guard.claim(
            user_id=7,
            idempotency_key="same-key",
            request_hash_value="hash-b",
            context=_context(),
        )


def test_uncertain_placement_blocks_retry(placement_factory):
    guard = PlacementGuardService(placement_factory)
    guard.claim(
        user_id=7,
        idempotency_key="uncertain-key",
        request_hash_value="hash-a",
        context=_context(),
    )
    guard.complete(
        user_id=7,
        idempotency_key="uncertain-key",
        status="uncertain",
        result={"results": []},
    )

    with pytest.raises(PlacementConflictError, match="Verify it in the broker app"):
        guard.claim(
            user_id=7,
            idempotency_key="uncertain-key",
            request_hash_value="hash-a",
            context=_context(),
        )


def test_placement_context_rejects_wrong_broker_selection():
    registry = SessionRegistry(broker_factory=DummyBrokerFactory())
    session = registry.create_session(
        broker_user_id="alice",
        broker_name="dummy",
        broker_config={},
        device_id="mobile",
    )
    session.user_record_id = 7
    session.trading_broker_connection_id = 42
    user = UserContext(
        user_id=7,
        email="user@example.com",
        role="user",
        device_id="mobile",
        active_broker_connection_id=99,
    )

    with pytest.raises(PlacementContextError, match="does not match"):
        validate_placement_context(
            registry=registry,
            session_id=session.session_id,
            user=user,
        )

    user.active_broker_connection_id = 42
    validated = validate_placement_context(
        registry=registry,
        session_id=session.session_id,
        user=user,
    )
    assert validated["broker_connection_id"] == 42


def test_placement_context_rejects_session_without_broker_connection():
    registry = SessionRegistry(broker_factory=DummyBrokerFactory())
    session = registry.create_session(
        broker_user_id="alice", broker_name="dummy", broker_config={}
    )
    user = UserContext(user_id=7, email="user@example.com", role="user")

    with pytest.raises(PlacementContextError, match="not bound"):
        validate_placement_context(
            registry=registry,
            session_id=session.session_id,
            user=user,
        )


def test_timeout_is_classified_as_uncertain_and_not_retried():
    broker = DummyBroker(fail=TimeoutError("Read timed out. Request did not complete"))
    session = DummySession()
    manager = GTTManager(broker, None, session)

    results = manager.place_orders(
        [
            {
                "symbol": "ABC",
                "exchange": "NSE",
                "price": 100,
                "trigger": 99,
                "qty": 1,
                "ltp": 101,
            }
        ]
    )

    assert results[0]["status"] == "Uncertain"
    assert broker.calls == 1
    assert session.refreshed == 1


def test_classify_broker_error_distinguishes_definitive_failures():
    assert classify_broker_error(ValueError("invalid lot size")) == "Fail"
    assert classify_broker_error(RuntimeError("502 Bad Gateway")) == "Uncertain"
