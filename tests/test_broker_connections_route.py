from __future__ import annotations

from api.routes import broker_connections as bc_routes


def test_browser_navigation_to_broker_connections_serves_spa(client, tmp_path, monkeypatch):
    index_path = tmp_path / "index.html"
    index_path.write_text("<html><body>spa</body></html>", encoding="utf-8")
    monkeypatch.setattr(bc_routes, "_UI_DIST_PATH", tmp_path)

    resp = client.get(
        "/broker-connections?oauth=success&broker=zerodha&reason=success",
        headers={
            "accept": "text/html,application/xhtml+xml",
            "sec-fetch-mode": "navigate",
        },
    )

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "<body>spa</body>" in resp.text


def test_api_request_to_broker_connections_returns_json(client):
    resp = client.get("/broker-connections", headers={"accept": "application/json"})

    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
