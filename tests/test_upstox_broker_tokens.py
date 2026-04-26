from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from brokers.upstox_broker import UpstoxBroker
from core.session_manager import SessionManager
from core.session_tokens import DbTokenStore
from db import models
from db.database import Base


@pytest.fixture
def sqlite_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    yield Session
    engine.dispose()


def test_upstox_broker_uses_session_token(sqlite_session, monkeypatch):
    session = sqlite_session()
    user = models.User(email="up@example.com", role="admin")
    session.add(user)
    session.flush()
    connection = models.BrokerConnection(
        user_id=user.id,
        broker_name="upstox",
        broker_user_id="UPUSER",
        metadata_json="{}",
    )
    session.add(connection)
    session.commit()
    connection_id = connection.id
    session.close()

    store = DbTokenStore(session_factory=sqlite_session)
    store.store_tokens(
        "upstox",
        {
            "access_token": "XYZ123",
            "broker_user_id": "UPUSER",
            "obtained_at": datetime.now(timezone.utc).isoformat(),
        },
        connection_id=connection_id,
    )

    session_manager = SessionManager(token_store=store)
    broker = UpstoxBroker(broker_user_id="UPUSER", api_key="key", api_secret="secret", redirect_uri="uri")
    broker.set_session_context(session_manager=session_manager, connection_id=connection_id)

    captured = {}

    class DummyResponse:
        status_code = 200

        def json(self):
            return {"data": []}

        def raise_for_status(self):
            return None

    def fake_get(url, headers):
        captured["auth"] = headers.get("Authorization")
        return DummyResponse()

    monkeypatch.setattr("requests.get", fake_get)

    broker.get_gtt_orders()
    assert captured["auth"] == "Bearer XYZ123"
