"""Mobile/desktop OAuth callback navigation safety."""

from __future__ import annotations

import urllib.parse

import pytest

from api import config


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = ""

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception("HTTP Error")


@pytest.fixture(autouse=True)
def oauth_env(monkeypatch):
    monkeypatch.setenv("KITE_API_KEY", "test-key")
    monkeypatch.setenv("KITE_API_SECRET", "test-secret")
    monkeypatch.setenv("KITE_REDIRECT_URI", "https://localhost/callback")
    monkeypatch.setenv("UPSTOX_API_KEY", "test-key")
    monkeypatch.setenv("UPSTOX_API_SECRET", "test-secret")
    monkeypatch.setenv("UPSTOX_REDIRECT_URI", "https://localhost/callback")
    monkeypatch.setattr(
        config, "OAUTH_FRONTEND_ORIGIN", "https://app.example.com"
    )
    monkeypatch.setattr(
        config,
        "OAUTH_FRONTEND_ORIGINS",
        ("https://app.example.com", "http://localhost:5173"),
    )
    monkeypatch.setattr(
        config,
        "OAUTH_RETURN_URL",
        "https://app.example.com/broker-connections",
    )


def test_mobile_zerodha_flow_redirects_without_tokens(client, monkeypatch):
    connect = client.get("/brokers/zerodha/connect", params={"flow": "mobile"})
    assert connect.status_code == 200
    connect_payload = connect.json()
    assert connect_payload["state"].startswith("mobile-")
    assert client.cookies.get("tradecraftx_oauth_flow") == "mobile"

    def fake_post(url, data, timeout):
        return FakeResponse(
            {"status": "success", "data": {"access_token": "secret", "user_id": "ZK1"}}
        )

    monkeypatch.setattr("api.routes.brokers.requests.post", fake_post)
    callback = client.get(
        "/brokers/zerodha/callback",
        params={"request_token": "req", "state": connect_payload["state"]},
    )

    assert callback.status_code == 200
    assert "Zerodha connected successfully" in callback.text
    assert "else if (mobile || topLevel)" in callback.text
    assert "window.location.replace(returnUrl)" in callback.text
    assert 'http-equiv="refresh"' in callback.text
    assert "Returning to TradeCraftX..." in callback.text
    assert "oauth=success" in callback.text
    assert "broker=zerodha" in callback.text
    assert "secret" not in callback.text
    assert "Return to TradeCraftX" in callback.text


def test_desktop_zerodha_flow_keeps_popup_behavior(client, monkeypatch):
    connect = client.get("/brokers/zerodha/connect")
    state = connect.json()["state"]
    assert state.startswith("popup-")

    def fake_post(url, data, timeout):
        return FakeResponse(
            {"status": "success", "data": {"access_token": "secret", "user_id": "ZK1"}}
        )

    monkeypatch.setattr("api.routes.brokers.requests.post", fake_post)
    callback = client.get(
        "/brokers/zerodha/callback",
        params={"request_token": "req", "state": state},
    )

    assert callback.status_code == 200
    assert "if (!mobile && !topLevel)" in callback.text
    assert "window.opener.postMessage" in callback.text
    assert "window.close()" in callback.text


def test_mobile_upstox_failure_returns_generic_error(client):
    # A client cannot choose an untrusted redirect; the state/cookie flow is used.
    client.get("/brokers/upstox/connect", params={"flow": "mobile"})
    callback = client.get(
        "/brokers/upstox/callback",
        params={"code": "abc", "state": "not-a-valid-state"},
    )

    assert callback.status_code == 400
    assert "window.location.replace" in callback.text
    assert "oauth=error" in callback.text
    assert "broker=upstox" in callback.text
    assert "Authorization failed" in callback.text
    assert "not-a-valid-state" not in callback.text


def test_connect_origin_cookie_controls_callback_origin(client, monkeypatch):
    """Same-origin/local Docker UI must not fall back to the Vite dev origin."""
    monkeypatch.setattr(
        config,
        "OAUTH_FRONTEND_ORIGINS",
        ("https://app.example.com", "http://localhost:8000"),
    )
    client.get(
        "/brokers/zerodha/connect",
        params={"flow": "mobile"},
        headers={"Origin": "http://localhost:8000"},
    )
    assert (
        urllib.parse.unquote(client.cookies.get("tradecraftx_oauth_origin") or "")
        == "http://localhost:8000"
    )

    callback = client.get(
        "/brokers/zerodha/callback",
        params={"request_token": "req", "state": "not-a-valid-state"},
    )
    assert "http://localhost:8000/broker-connections" in callback.text
    assert "app.example.com" not in callback.text


def test_callback_never_accepts_arbitrary_return_url(client, monkeypatch):
    connect = client.get("/brokers/zerodha/connect", params={"flow": "mobile"})
    state = connect.json()["state"]

    def fake_post(url, data, timeout):
        return FakeResponse(
            {"status": "success", "data": {"access_token": "secret", "user_id": "ZK1"}}
        )

    monkeypatch.setattr("api.routes.brokers.requests.post", fake_post)
    callback = client.get(
        "/brokers/zerodha/callback",
        params={
            "request_token": "req",
            "state": state,
            "return_url": "https://evil.example.com/steal",
        },
    )
    assert "evil.example.com" not in callback.text
    assert "app.example.com" in callback.text
