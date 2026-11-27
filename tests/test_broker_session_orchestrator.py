"""Broker session orchestration - explicit activation and device-scoped switching."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from api import config
from core.auth.active_connection_store import get_active_connection_store
from core.auth.context import UserContext


class DummyBroker:
    TRANSACTION_TYPE_BUY = "BUY"

    def __init__(self, broker_name, broker_user_id, config):
        self.broker_name = broker_name
        self.broker_user_id = broker_user_id
        self.config = config
        self.connection_id = None

    def set_session_context(self, session_manager, connection_id):
        self.connection_id = connection_id

    def login(self):
        pass

    def get_holdings(self):
        return []

    def get_gtt_orders(self):
        return []

    def get_positions(self):
        return {"net": [], "day": []}

    def get_funds(self):
        return {}

    def get_margins(self):
        return {}


@pytest.fixture(autouse=True)
def clean_session_state():
    store = get_active_connection_store()
    for user_id in (1, 2, 99):
        store.clear_all_for_user(user_id)
    yield
    for user_id in (1, 2, 99):
        store.clear_all_for_user(user_id)


@pytest.fixture(autouse=True)
def fake_broker(monkeypatch):
    monkeypatch.setattr(
        "core.runtime.session_registry.BrokerFactory.get_broker",
        lambda broker_name, broker_user_id, config: DummyBroker(
            broker_name, broker_user_id, config
        ),
    )


def _user(device: str = "mobile", user_id: int = 1) -> UserContext:
    return UserContext(
        user_id=user_id,
        email="user@example.com",
        role="user",
        device_id=device,
    )


def _connect(client, broker_name: str, broker_user_id: str, user_id: int = 1) -> int:
    connection = client.app.state.test_broker_connection_service.create_connection(
        user_id=user_id, broker_name=broker_name
    )
    client.app.state.test_session_manager.store_tokens(
        broker_name,
        {
            "access_token": f"{broker_name}-token",
            "broker_user_id": broker_user_id,
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        },
        connection_id=connection.id,
    )
    return connection.id


# --- Phase 1: explicit activation ---


def test_login_does_not_start_session_or_activate_broker(client):
    """No-arg orchestrate must not auto-activate a single connected broker."""
    connection_id = _connect(client, "upstox", "UP1")
    orchestrator = client.app.state.test_orchestrator

    result = orchestrator.orchestrate(_user(), warm_start=False)

    assert result.status.value == "CONNECTED"
    assert result.session_id is None
    assert result.broker_connected is True
    assert "Select a broker" in (result.message or "")
    assert client.app.state.test_session_registry.active_sessions() == 0
    assert get_active_connection_store().get_active_connection(1, "mobile") is None
    # Connection still exists and token is still stored
    assert client.app.state.test_session_manager.get_token_bundle(
        "upstox", connection_id=connection_id
    )


def test_no_broker_connected_returns_actionable_error(client):
    result = client.app.state.test_orchestrator.orchestrate(_user(), warm_start=False)

    assert result.status.value == "ERROR"
    assert result.broker_connected is False
    assert "Connect a broker" in (result.message or "")


def test_explicit_zerodha_activation(client):
    connection_id = _connect(client, "zerodha", "ZK1")
    orchestrator = client.app.state.test_orchestrator

    result = orchestrator.orchestrate(
        _user(), broker_connection_id=connection_id, warm_start=False
    )

    assert result.status.value == "READY"
    assert result.connection_id == connection_id
    assert result.broker_name == "zerodha"
    assert result.session_id
    assert get_active_connection_store().get_active_connection(1, "mobile") == connection_id


def test_explicit_upstox_activation(client):
    connection_id = _connect(client, "upstox", "UP1")
    orchestrator = client.app.state.test_orchestrator

    result = orchestrator.orchestrate(
        _user(), broker_connection_id=connection_id, warm_start=False
    )

    assert result.status.value == "READY"
    assert result.connection_id == connection_id
    assert result.broker_name == "upstox"
    assert result.session_id
    assert get_active_connection_store().get_active_connection(1, "mobile") == connection_id


def test_new_session_requests_warm_start_by_default(client, monkeypatch):
    connection_id = _connect(client, "upstox", "UP1")
    calls = []

    def fake_start(**kwargs):
        calls.append(kwargs)
        return {
            "session_id": "session-1",
            "broker": "upstox",
            "broker_user_id": "UP1",
            "warm_start": True,
        }

    monkeypatch.setattr(client.app.state.test_session_service, "start_session", fake_start)

    result = client.app.state.test_orchestrator.orchestrate(
        _user(), broker_connection_id=connection_id
    )

    assert result.status.value == "READY"
    assert calls == [
        {"broker_connection_id": connection_id, "warm_start": True, "device_id": "mobile"}
    ]


def test_existing_device_session_is_reused_without_duplicate(client, monkeypatch):
    connection_id = _connect(client, "zerodha", "ZK1")
    orchestrator = client.app.state.test_orchestrator
    refreshed = []

    def fake_refresh(session_id):
        refreshed.append(session_id)
        return {"session_id": session_id, "broker": "zerodha", "broker_user_id": "ZK1"}

    monkeypatch.setattr(client.app.state.test_session_service, "refresh_caches", fake_refresh)

    first = orchestrator.orchestrate(
        _user(), broker_connection_id=connection_id, warm_start=False
    )
    # no-arg recovery should reuse same device session
    second = orchestrator.orchestrate(_user(), warm_start=False)

    assert first.status.value == "READY"
    assert second.status.value == "READY"
    assert second.session_id == first.session_id
    assert refreshed == [first.session_id]
    assert client.app.state.test_session_registry.active_sessions() == 1


def test_multiple_accounts_for_one_broker_require_explicit_selection(client):
    _connect(client, "upstox", "UP1")
    _connect(client, "upstox", "UP2")

    result = client.app.state.test_orchestrator.orchestrate(_user(), warm_start=False)

    assert result.status.value == "CONNECTED"
    assert result.session_id is None
    assert len(result.candidates) == 2
    assert client.app.state.test_session_registry.active_sessions() == 0


def test_both_brokers_connected_require_explicit_selection(client):
    _connect(client, "upstox", "UP1")
    _connect(client, "zerodha", "ZK1")

    result = client.app.state.test_orchestrator.orchestrate(_user(), warm_start=False)

    assert result.status.value == "CONNECTED"
    assert result.session_id is None
    assert len(result.candidates) == 2
    assert client.app.state.test_session_registry.active_sessions() == 0


def test_switching_zerodha_to_upstox(client):
    zerodha_id = _connect(client, "zerodha", "ZK1")
    upstox_id = _connect(client, "upstox", "UP1")
    orchestrator = client.app.state.test_orchestrator

    first = orchestrator.orchestrate(
        _user(), broker_connection_id=zerodha_id, warm_start=False
    )
    second = orchestrator.orchestrate(
        _user(), broker_connection_id=upstox_id, warm_start=False
    )

    assert first.status.value == "READY"
    assert second.status.value == "READY"
    assert second.broker_name == "upstox"
    assert second.connection_id == upstox_id
    assert second.session_id != first.session_id
    assert get_active_connection_store().get_active_connection(1, "mobile") == upstox_id
    # Old device session deactivated; only one active session for this device.
    assert client.app.state.test_session_registry.active_sessions() == 1
    assert (
        client.app.state.test_session_registry.find_session_for_connection(
            1, "mobile", zerodha_id
        )
        is None
    )
    assert (
        client.app.state.test_session_registry.find_session_for_connection(
            1, "mobile", upstox_id
        )
        is not None
    )


def test_switching_upstox_to_zerodha(client):
    upstox_id = _connect(client, "upstox", "UP1")
    zerodha_id = _connect(client, "zerodha", "ZK1")
    orchestrator = client.app.state.test_orchestrator

    first = orchestrator.orchestrate(
        _user(), broker_connection_id=upstox_id, warm_start=False
    )
    second = orchestrator.orchestrate(
        _user(), broker_connection_id=zerodha_id, warm_start=False
    )

    assert first.status.value == "READY"
    assert second.status.value == "READY"
    assert second.broker_name == "zerodha"
    assert get_active_connection_store().get_active_connection(1, "mobile") == zerodha_id
    assert client.app.state.test_session_registry.active_sessions() == 1


def test_failed_broker_switch_preserves_old_session(client, monkeypatch):
    zerodha_id = _connect(client, "zerodha", "ZK1")
    upstox_id = _connect(client, "upstox", "UP1")
    orchestrator = client.app.state.test_orchestrator

    first = orchestrator.orchestrate(
        _user(), broker_connection_id=zerodha_id, warm_start=False
    )
    assert first.status.value == "READY"

    real_start = client.app.state.test_session_service.start_session

    def fail_upstox(**kwargs):
        if kwargs.get("broker_connection_id") == upstox_id:
            raise RuntimeError("upstox unavailable")
        return real_start(**kwargs)

    monkeypatch.setattr(client.app.state.test_session_service, "start_session", fail_upstox)

    result = orchestrator.orchestrate(
        _user(), broker_connection_id=upstox_id, warm_start=False
    )

    assert result.status.value == "READY"
    assert result.connection_id == zerodha_id
    assert result.session_id == first.session_id
    assert "current session is still active" in (result.message or "").lower()
    assert get_active_connection_store().get_active_connection(1, "mobile") == zerodha_id
    assert (
        client.app.state.test_session_registry.find_session_for_connection(
            1, "mobile", zerodha_id
        )
        is not None
    )


def test_broker_tokens_remain_stored_after_switching(client):
    zerodha_id = _connect(client, "zerodha", "ZK1")
    upstox_id = _connect(client, "upstox", "UP1")
    orchestrator = client.app.state.test_orchestrator

    orchestrator.orchestrate(_user(), broker_connection_id=zerodha_id, warm_start=False)
    orchestrator.orchestrate(_user(), broker_connection_id=upstox_id, warm_start=False)

    assert client.app.state.test_session_manager.get_token_bundle(
        "zerodha", connection_id=zerodha_id
    )
    assert client.app.state.test_session_manager.get_token_bundle(
        "upstox", connection_id=upstox_id
    )


def test_session_expiration_recovery_preserves_selected_broker(client):
    connection_id = _connect(client, "zerodha", "ZK1")
    orchestrator = client.app.state.test_orchestrator
    registry = client.app.state.test_session_registry

    first = orchestrator.orchestrate(
        _user(), broker_connection_id=connection_id, warm_start=False
    )
    assert first.status.value == "READY"

    # Simulate expired/lost in-memory session while active connection remains selected.
    registry.evict(first.session_id)
    assert registry.active_sessions() == 0
    assert get_active_connection_store().get_active_connection(1, "mobile") == connection_id

    recovered = orchestrator.orchestrate(_user(), warm_start=False)

    assert recovered.status.value == "READY"
    assert recovered.connection_id == connection_id
    assert recovered.broker_name == "zerodha"
    assert recovered.session_id
    assert recovered.session_id != first.session_id


def test_desktop_mobile_device_isolation(client):
    connection_id = _connect(client, "upstox", "UP1")
    orchestrator = client.app.state.test_orchestrator

    laptop = orchestrator.orchestrate(
        _user("laptop"), broker_connection_id=connection_id, warm_start=False
    )
    mobile = orchestrator.orchestrate(
        _user("mobile"), broker_connection_id=connection_id, warm_start=False
    )

    assert laptop.status.value == "READY"
    assert mobile.status.value == "READY"
    assert laptop.session_id != mobile.session_id
    assert get_active_connection_store().get_active_connection(1, "laptop") == connection_id
    assert get_active_connection_store().get_active_connection(1, "mobile") == connection_id
    assert client.app.state.test_session_registry.active_sessions() == 2


def test_initialization_failure_keeps_connection_reported_as_connected(client, monkeypatch):
    connection_id = _connect(client, "upstox", "UP1")

    def fail(**_kwargs):
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr(client.app.state.test_session_service, "start_session", fail)

    result = client.app.state.test_orchestrator.orchestrate(
        _user(), broker_connection_id=connection_id, warm_start=False
    )

    assert result.status.value == "ERROR"
    assert result.broker_connected is True
    assert result.connection_id == connection_id
    assert result.message == "Broker connected. Session initialization failed."
    assert get_active_connection_store().get_active_connection(1, "mobile") is None


def test_orchestrate_endpoint_explicit_activation(client):
    connection_id = _connect(client, "upstox", "UP1")
    response = client.post(
        "/session/orchestrate",
        json={"broker_connection_id": connection_id, "warm_start": False},
        headers={"X-Device-Id": "mobile"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "READY"
    assert payload["connection_id"] == connection_id
    assert get_active_connection_store().get_active_connection(1, "mobile") == connection_id


def test_orchestrate_endpoint_without_target_does_not_activate(client):
    """A plain session check after login must never pick a broker."""
    _connect(client, "zerodha", "ZK1")

    response = client.post(
        "/session/orchestrate",
        json={"warm_start": False},
        headers={"X-Device-Id": "mobile"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "CONNECTED"
    assert payload["session_id"] is None
    assert client.app.state.test_session_registry.active_sessions() == 0
    assert get_active_connection_store().get_active_connection(1, "mobile") is None


def test_oauth_completion_starts_selected_session(client, monkeypatch):
    """OAuth callbacks only persist tokens; the UI then activates that connection."""
    monkeypatch.setattr(config, "KITE_API_KEY", "test-key")
    monkeypatch.setattr(config, "KITE_API_SECRET", "test-secret")
    monkeypatch.setattr(
        config, "KITE_REDIRECT_URI", "http://localhost:8000/brokers/zerodha/callback"
    )

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": "success",
                "data": {
                    "access_token": "kite-token",
                    "public_token": "kite-public",
                    "user_id": "ZK-OAUTH",
                },
            }

    connect = client.get("/brokers/zerodha/connect")
    assert connect.status_code == 200
    connect_payload = connect.json()
    connection_id = connect_payload["connection_id"]

    monkeypatch.setattr(
        "api.routes.brokers.requests.post", lambda *args, **kwargs: FakeResponse()
    )
    callback = client.get(
        "/brokers/zerodha/callback",
        params={"request_token": "req123", "state": connect_payload["state"]},
    )
    assert callback.status_code == 200
    assert "connected successfully" in callback.text
    # OAuth alone does not start a trading session.
    assert client.app.state.test_session_registry.active_sessions() == 0

    response = client.post(
        "/session/orchestrate",
        json={"broker_connection_id": connection_id, "warm_start": False},
        headers={"X-Device-Id": "mobile"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "READY"
    assert payload["connection_id"] == connection_id
    assert payload["broker_name"] == "zerodha"
    assert payload["session_id"]
    assert client.app.state.test_session_registry.active_sessions() == 1
    assert get_active_connection_store().get_active_connection(1, "mobile") == connection_id


def test_no_stale_broker_data_after_switching(client):
    zerodha_id = _connect(client, "zerodha", "ZK1")
    upstox_id = _connect(client, "upstox", "UP1")
    orchestrator = client.app.state.test_orchestrator
    registry = client.app.state.test_session_registry

    orchestrator.orchestrate(
        _user(), broker_connection_id=zerodha_id, warm_start=False
    )
    second = orchestrator.orchestrate(
        _user(), broker_connection_id=upstox_id, warm_start=False
    )

    assert second.status.value == "READY"
    assert registry.find_session_for_connection(1, "mobile", zerodha_id) is None
    active = registry.find_session_for_connection(1, "mobile", upstox_id)
    assert active is not None
    assert active.session_id == second.session_id
    assert active.broker_name == "upstox"
    # Only the active device session remains.
    assert registry.active_sessions() == 1
