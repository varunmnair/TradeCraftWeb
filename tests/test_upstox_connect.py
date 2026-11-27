import os
from datetime import datetime, timedelta, timezone

import pytest

from api.routes.broker_connections import get_service
from db import models


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    @property
    def text(self):
        import json
        return json.dumps(self._payload)

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def upstox_env(monkeypatch):
    monkeypatch.setenv("UPSTOX_API_KEY", "test-key")
    monkeypatch.setenv("UPSTOX_API_SECRET", "test-secret")
    monkeypatch.setenv("UPSTOX_REDIRECT_URI", "https://localhost/callback")


def test_upstox_connect_and_callback(client, monkeypatch):
    connect_resp = client.get("/brokers/upstox/connect")
    assert connect_resp.status_code == 200
    payload = connect_resp.json()
    assert "authorize_url" in payload
    state = payload["state"]
    connection_id = payload["connection_id"]

    def fake_post(url, data, timeout):
        assert "authorization/token" in url
        return FakeResponse({
            "access_token": "token123",
            "refresh_token": "refresh123",
            "expires_in": "3600",
            "token_type": "bearer",
            "scope": "orders",
            "user_id": "UP123",
        })

    monkeypatch.setattr("api.routes.brokers.requests.post", fake_post)

    cb_resp = client.get("/brokers/upstox/callback", params={"code": "abc", "state": state})
    assert cb_resp.status_code == 200
    assert "connected successfully" in cb_resp.text

    status_resp = client.get("/brokers/upstox/status")
    assert status_resp.status_code == 200
    statuses = status_resp.json()["connections"]
    assert any(item["connected"] for item in statuses)


def test_repeated_connect_reuses_one_connection_and_hides_placeholders(client):
    first = client.get("/brokers/upstox/connect").json()
    second = client.get("/brokers/upstox/connect").json()
    assert first["connection_id"] == second["connection_id"]
    connection_id = first["connection_id"]

    service = client.app.state.test_broker_connection_service
    # This route resolves its service directly, so point it at the test DB.
    client.app.dependency_overrides[get_service] = lambda: service
    with service._session_factory() as session:
        connection = session.get(models.BrokerConnection, connection_id)
        session.add(
            models.BrokerConnection(
                user_id=connection.user_id,
                broker_name="upstox",
                metadata_json="{}",
            )
        )
        session.commit()

    # Placeholders are hidden until OAuth actually stores tokens.
    assert client.get("/brokers/upstox/status").json()["connections"] == []
    assert client.get("/broker-connections").json() == []

    client.app.state.test_session_manager.store_tokens(
        "upstox",
        {
            "access_token": "token123",
            "broker_user_id": "UP123",
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        },
        connection_id=connection_id,
    )
    statuses = client.get("/brokers/upstox/status").json()["connections"]
    assert [status["connection_id"] for status in statuses] == [connection_id]
    listed = client.get("/broker-connections").json()
    assert [item["id"] for item in listed] == [connection_id]


def test_upstox_callback_invalid_state(client):
    response = client.get("/brokers/upstox/callback", params={"code": "abc", "state": "invalid"})
    assert response.status_code == 400
    assert "failed" in response.text


def test_upstox_callback_expired_state(client):
    connect_resp = client.get("/brokers/upstox/connect")
    state = connect_resp.json()["state"]

    service = client.app.state.test_auth_state_service
    with service._session_factory() as session:  # pylint: disable=protected-access
        session.query(models.BrokerAuthState).filter(models.BrokerAuthState.state_token == state).delete()
        session.commit()

    resp = client.get("/brokers/upstox/callback", params={"code": "abc", "state": state})
    assert resp.status_code == 400
    assert "failed" in resp.text


def test_upstox_callback_replaces_stale_token(client, monkeypatch):
    connect_resp = client.get("/brokers/upstox/connect")
    assert connect_resp.status_code == 200
    payload = connect_resp.json()
    state = payload["state"]
    connection_id = payload["connection_id"]

    # Pre-store an expired/stale token to simulate the reported reconnect loop.
    client.app.state.test_session_manager.store_tokens(
        "upstox",
        {
            "access_token": "stale-token",
            "broker_user_id": "UP123",
            "expires_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        },
        connection_id=connection_id,
    )

    def fake_post(url, data, timeout):
        assert "authorization/token" in url
        return FakeResponse(
            {
                "access_token": "fresh-token",
                "refresh_token": "refresh123",
                "expires_in": "3600",
                "token_type": "bearer",
                "scope": "orders",
                "user_id": "UP123",
            }
        )

    monkeypatch.setattr("api.routes.brokers.requests.post", fake_post)

    cb_resp = client.get("/brokers/upstox/callback", params={"code": "abc", "state": state})
    assert cb_resp.status_code == 200
    assert "connected successfully" in cb_resp.text

    bundle = client.app.state.test_session_manager.get_token_bundle("upstox", connection_id=connection_id)
    assert bundle is not None
    assert bundle.access_token == "fresh-token"
