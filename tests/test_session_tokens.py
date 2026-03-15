import json

from sqlalchemy.orm import sessionmaker

from datetime import datetime, timezone

import pytest

from core.runtime.session_registry import SessionRegistry
from core.session_manager import SessionManager
from core.session_tokens import DbTokenStore
from db import models


class DummyBroker:
    def __init__(self, broker_name, user_id, config):
        self.broker_name = broker_name
        self.user_id = user_id
        self.config = config


def test_db_token_store_roundtrip(engine):
    SessionTesting = sessionmaker(bind=engine)
    store = DbTokenStore(session_factory=SessionTesting)

    with SessionTesting() as session:
        tenant = models.Tenant(name="TenantA")
        session.add(tenant)
        session.flush()
        user = models.User(tenant_id=tenant.id, email="a@example.com", hashed_password="hash", role="admin")
        session.add(user)
        session.flush()
        connection = models.BrokerConnection(
            tenant_id=tenant.id,
            user_id=user.id,
            broker_name="zerodha",
            metadata_json=json.dumps({}),
        )
        session.add(connection)
        session.commit()
        connection_id = connection.id

    now = datetime.now(timezone.utc)
    store.store_tokens(
        "zerodha",
        {
            "access_token": "ACCESS123",
            "extended_token": "EXT456",
            "broker_user_id": "BROKERID",
            "raw_profile": {"name": "User"},
            "obtained_at": now.isoformat(),
            "expires_at": now.replace(hour=now.hour + 1).isoformat(),
        },
        connection_id=connection_id,
    )

    bundle = store.get_tokens("zerodha", connection_id=connection_id)
    assert bundle is not None
    assert bundle.access_token == "ACCESS123"
    assert bundle.broker_user_id == "BROKERID"
    assert bundle.raw_profile["name"] == "User"


def test_session_registry_reads_tokens_from_db(engine, monkeypatch):
    SessionTesting = sessionmaker(bind=engine)
    store = DbTokenStore(session_factory=SessionTesting)
    session_manager = SessionManager(token_store=store, dev_mode=False)

    def fake_get_broker(broker_name, user_id, config):
        return DummyBroker(broker_name, user_id, config)

    monkeypatch.setattr("core.runtime.session_registry.BrokerFactory.get_broker", fake_get_broker)

    registry = SessionRegistry(
        session_factory=SessionTesting,
        session_manager=session_manager,
    )

    with SessionTesting() as session:
        tenant = models.Tenant(name="TenantB")
        session.add(tenant)
        session.flush()
        user = models.User(tenant_id=tenant.id, email="b@example.com", hashed_password="hash", role="admin")
        session.add(user)
        session.flush()
        
        # Create Upstox connection for market data (required for Zerodha trading)
        upstox_connection = models.BrokerConnection(
            tenant_id=tenant.id,
            user_id=user.id,
            broker_name="upstox",
            metadata_json=json.dumps({"api_key": "UPSTOX_KEY"}),
        )
        session.add(upstox_connection)
        session.flush()
        
        # Create Zerodha connection for trading
        connection = models.BrokerConnection(
            tenant_id=tenant.id,
            user_id=user.id,
            broker_name="zerodha",
            metadata_json=json.dumps({"api_key": "API123"}),
        )
        session.add(connection)
        session.commit()
        connection_id = connection.id
        upstox_connection_id = upstox_connection.id
        tenant_id = tenant.id
        user_id = user.id

    store.store_tokens(
        "upstox",
        {
            "access_token": "UPSTOX_ACCESS",
            "broker_user_id": "UPSTOX_USER",
        },
        connection_id=upstox_connection_id,
    )
    
    store.store_tokens(
        "zerodha",
        {
            "access_token": "ACCESS456",
            "extended_token": "EXT456",
            "broker_user_id": "BROKER456",
            "api_secret": "secret",
        },
        connection_id=connection_id,
    )

    context = registry.create_session(broker_connection_id=connection_id)
    assert context.user_id == "BROKER456"
    assert context.tenant_id == tenant_id
    assert context.session_cache.broker.config["access_token"] == "ACCESS456"
    # Verify market data connection is set
    assert context.market_data_connection_id == upstox_connection_id


def test_session_manager_access_token_from_db(engine):
    SessionTesting = sessionmaker(bind=engine)
    store = DbTokenStore(session_factory=SessionTesting)
    session_manager = SessionManager(token_store=store, dev_mode=False)

    with SessionTesting() as session:
        tenant = models.Tenant(name="TenantC")
        session.add(tenant)
        session.flush()
        user = models.User(tenant_id=tenant.id, email="c@example.com", hashed_password="hash", role="admin")
        session.add(user)
        session.flush()
        connection = models.BrokerConnection(
            tenant_id=tenant.id,
            user_id=user.id,
            broker_name="zerodha",
            metadata_json=json.dumps({}),
        )
        session.add(connection)
        session.commit()
        connection_id = connection.id

    store.store_tokens(
        "zerodha",
        {"access_token": "TOKEN789", "broker_user_id": "BROKER789"},
        connection_id=connection_id,
    )

    token = session_manager.get_access_token("zerodha", connection_id=connection_id)
    assert token == "TOKEN789"
