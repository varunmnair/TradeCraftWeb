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


def test_zerodha_connect_requires_upstox(client):
    resp = client.get("/brokers/zerodha/connect")
    assert resp.status_code == 409
    payload = resp.json()
    assert payload["error_code"] == "upstox_required"
    assert "Upstox connection required" in payload["message"]


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
    # 1. Connect Upstox (prerequisite)
    upstox_connect = client.get("/brokers/upstox/connect")
    upstox_state = upstox_connect.json()["state"]

    def fake_upstox_post(url, data, timeout):
        return FakeResponse({"access_token": "upstox-token", "user_id": "UPSTOX123"})

    monkeypatch.setattr("api.routes.brokers.requests.post", fake_upstox_post)
    client.get("/brokers/upstox/callback", params={"code": "abc", "state": upstox_state})

    # 2. Connect Zerodha
    connect_resp = client.get("/brokers/zerodha/connect")
    assert connect_resp.status_code == 200
    payload = connect_resp.json()
    assert "authorize_url" in payload
    assert "v=3" in payload["authorize_url"]
    state = payload["state"]
    zerodha_connection_id = payload["connection_id"]

    # 3. Mock Kite token exchange and run callback
    def fake_kite_post(url, data, timeout):
        assert "session/token" in url
        assert data["api_key"] == "test-key"
        # Kite returns access_token nested in "data"
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

    # 4. Check status filtered by connection_id
    status_resp = client.get(f"/brokers/zerodha/status?connection_id={zerodha_connection_id}")
    assert status_resp.status_code == 200
    statuses = status_resp.json()["connections"]
    assert len(statuses) == 1
    assert statuses[0]["connected"] is True
    assert statuses[0]["broker_user_id"] == "ZK1234"


def test_zerodha_callback_invalid_state(client, monkeypatch):
    # Connect upstox first to pass the /connect check, though we call /callback directly
    connect_upstox_for_test(client, monkeypatch)
    response = client.get(
        "/brokers/zerodha/callback", params={"request_token": "abc", "state": "invalid-state"}
    )
    assert response.status_code == 400
    assert "failed" in response.text