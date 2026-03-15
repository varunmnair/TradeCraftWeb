import os

import pytest

from db import models


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

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
