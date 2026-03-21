import pytest


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception("HTTP Error")


@pytest.fixture(autouse=True)
def kite_env(monkeypatch):
    monkeypatch.setenv("KITE_API_KEY", "test-key")
    monkeypatch.setenv("KITE_API_SECRET", "test-secret")
    monkeypatch.setenv("KITE_REDIRECT_URI", "https://localhost/callback")


@pytest.fixture(autouse=True)
def upstox_env(monkeypatch):
    monkeypatch.setenv("UPSTOX_API_KEY", "test-key")
    monkeypatch.setenv("UPSTOX_API_SECRET", "test-secret")
    monkeypatch.setenv("UPSTOX_REDIRECT_URI", "https://localhost/callback")


def test_zerodha_connect_independent_of_upstox(client):
    """Zerodha can now be connected without Upstox - they are independent."""
    resp = client.get("/brokers/zerodha/connect")
    assert resp.status_code == 200
    payload = resp.json()
    assert "authorize_url" in payload
    assert "state" in payload
    assert "connection_id" in payload


def connect_upstox_for_test(client, monkeypatch):
    """Helper to connect upstox first to satisfy prerequisite."""
    connect_resp = client.get("/brokers/upstox/connect")
    assert connect_resp.status_code == 200
    state = connect_resp.json()["state"]

    def fake_post(url, data, timeout):
        return FakeResponse({"access_token": "upstox-token", "user_id": "UPSTOX123"})

    monkeypatch.setattr("api.routes.brokers.requests.post", fake_post)
    cb_resp = client.get("/brokers/upstox/callback", params={"code": "abc", "state": state})
    assert cb_resp.status_code == 200


def test_zerodha_connect_and_callback(client, monkeypatch):
    # 1. Connect Zerodha directly (no Upstox prerequisite)
    connect_resp = client.get("/brokers/zerodha/connect")
    assert connect_resp.status_code == 200
    payload = connect_resp.json()
    assert "authorize_url" in payload
    assert "v=3" in payload["authorize_url"]
    state = payload["state"]
    zerodha_connection_id = payload["connection_id"]

    # 2. Mock Kite token exchange and run callback
    def fake_kite_post(url, data, timeout):
        assert "session/token" in url
        # Don't check api_key since it comes from env
        return FakeResponse({
            "status": "success",
            "data": {
                "access_token": "kite-token",
                "public_token": "kite-public",
                "user_id": "ZK1234"
            }
        })

    monkeypatch.setattr("api.routes.brokers.requests.post", fake_kite_post)

    cb_resp = client.get("/brokers/zerodha/callback", params={"request_token": "req123", "state": state})
    assert cb_resp.status_code == 200
    assert "Zerodha connected successfully" in cb_resp.text

    # 3. Check status filtered by connection_id
    status_resp = client.get(f"/brokers/zerodha/status?connection_id={zerodha_connection_id}")
    assert status_resp.status_code == 200
    statuses = status_resp.json()["connections"]
    assert len(statuses) == 1
    assert statuses[0]["connected"] is True
    assert statuses[0]["broker_user_id"] == "ZK1234"


def test_zerodha_callback_invalid_state(client):
    """Invalid state token should return error even without Upstox."""
    response = client.get(
        "/brokers/zerodha/callback", params={"request_token": "abc", "state": "invalid-state"}
    )
    assert response.status_code == 400
    assert "failed" in response.text