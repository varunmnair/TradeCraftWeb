"""Tests for dual-broker session support (Zerodha trading + Upstox market data)."""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.session_manager import SessionManager
from core.session_tokens import DbTokenStore
from core.runtime.session_registry import SessionRegistry
from db import models
from db.database import Base


class DummyBroker:
    """Dummy broker for testing."""
    def __init__(self, broker_name, broker_user_id, config):
        self.broker_name = broker_name
        self.broker_user_id = broker_user_id
        self.config = config
        self.connection_id = None

    def set_session_context(self, session_manager, connection_id):
        self.connection_id = connection_id

    def login(self):
        pass


@pytest.fixture
def engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


def test_zerodha_session_works_without_upstox(engine, monkeypatch):
    """Starting a Zerodha session should work even without Upstox - market data is optional."""
    SessionTesting = sessionmaker(bind=engine)
    store = DbTokenStore(session_factory=SessionTesting)
    session_manager = SessionManager(token_store=store, dev_mode=False)

    def fake_get_broker(broker_name, broker_user_id, config):
        return DummyBroker(broker_name, broker_user_id, config)

    monkeypatch.setattr("core.runtime.session_registry.BrokerFactory.get_broker", fake_get_broker)

    registry = SessionRegistry(
        session_factory=SessionTesting,
        session_manager=session_manager,
    )

    with SessionTesting() as session:
        user = models.User(email="test@example.com", role="admin")
        session.add(user)
        session.flush()
        
        # Only create Zerodha connection, no Upstox
        connection = models.BrokerConnection(
            user_id=user.id,
            broker_name="zerodha",
            broker_user_id="ZERODHA_USER",
            metadata_json=json.dumps({"api_key": "KITE_KEY"}),
        )
        session.add(connection)
        session.commit()
        zerodha_connection_id = connection.id

    store.store_tokens(
        "zerodha",
        {"access_token": "ZERODHA_TOKEN", "broker_user_id": "ZERODHA_USER"},
        connection_id=zerodha_connection_id,
    )

    # Should succeed - market data (Upstox) is optional
    context = registry.create_session(broker_connection_id=zerodha_connection_id)
    assert context is not None
    assert context.trading_broker_connection_id == zerodha_connection_id
    # Market data connection should be None since no Upstox
    assert context.market_data_connection_id is None


def test_zerodha_session_succeeds_with_upstox(engine, monkeypatch):
    """Starting a Zerodha session should succeed when both connections exist - Upstox auto-selected for market data."""
    SessionTesting = sessionmaker(bind=engine)
    store = DbTokenStore(session_factory=SessionTesting)
    session_manager = SessionManager(token_store=store, dev_mode=False)

    def fake_get_broker(broker_name, broker_user_id, config):
        return DummyBroker(broker_name, broker_user_id, config)

    monkeypatch.setattr("core.runtime.session_registry.BrokerFactory.get_broker", fake_get_broker)

    registry = SessionRegistry(
        session_factory=SessionTesting,
        session_manager=session_manager,
    )

    with SessionTesting() as session:
        user = models.User(email="test2@example.com", role="admin")
        session.add(user)
        session.flush()
        
        # Create Upstox connection for market data
        upstox_connection = models.BrokerConnection(
            user_id=user.id,
            broker_name="upstox",
            broker_user_id="UPSTOX_USER",
            metadata_json=json.dumps({"api_key": "UPSTOX_KEY"}),
        )
        session.add(upstox_connection)
        session.flush()
        
        # Create Zerodha connection for trading
        zerodha_connection = models.BrokerConnection(
            user_id=user.id,
            broker_name="zerodha",
            broker_user_id="ZERODHA_USER",
            metadata_json=json.dumps({"api_key": "KITE_KEY"}),
        )
        session.add(zerodha_connection)
        session.commit()
        zerodha_connection_id = zerodha_connection.id
        upstox_connection_id = upstox_connection.id

    # Store tokens for both
    store.store_tokens(
        "upstox",
        {"access_token": "UPSTOX_TOKEN", "broker_user_id": "UPSTOX_USER"},
        connection_id=upstox_connection_id,
    )
    store.store_tokens(
        "zerodha",
        {"access_token": "ZERODHA_TOKEN", "broker_user_id": "ZERODHA_USER"},
        connection_id=zerodha_connection_id,
    )

    # Should succeed with auto-selected Upstox
    context = registry.create_session(broker_connection_id=zerodha_connection_id)
    
    assert context.broker_name == "zerodha"
    assert context.trading_broker_connection_id == zerodha_connection_id
    assert context.market_data_connection_id == upstox_connection_id
    assert context.session_cache.market_data_connection_id == upstox_connection_id


def test_upstox_session_uses_same_connection(engine, monkeypatch):
    """Upstox session should use the same connection for trading and market data."""
    SessionTesting = sessionmaker(bind=engine)
    store = DbTokenStore(session_factory=SessionTesting)
    session_manager = SessionManager(token_store=store, dev_mode=False)

    def fake_get_broker(broker_name, broker_user_id, config):
        return DummyBroker(broker_name, broker_user_id, config)

    monkeypatch.setattr("core.runtime.session_registry.BrokerFactory.get_broker", fake_get_broker)

    registry = SessionRegistry(
        session_factory=SessionTesting,
        session_manager=session_manager,
    )

    with SessionTesting() as session:
        user = models.User(email="test3@example.com", role="admin")
        session.add(user)
        session.flush()
        
        # Create Upstox connection
        connection = models.BrokerConnection(
            user_id=user.id,
            broker_name="upstox",
            broker_user_id="UPSTOX_USER",
            metadata_json=json.dumps({"api_key": "UPSTOX_KEY"}),
        )
        session.add(connection)
        session.commit()
        connection_id = connection.id

    store.store_tokens(
        "upstox",
        {"access_token": "UPSTOX_TOKEN", "broker_user_id": "UPSTOX_USER"},
        connection_id=connection_id,
    )

    context = registry.create_session(broker_connection_id=connection_id)
    
    assert context.broker_name == "upstox"
    assert context.trading_broker_connection_id == connection_id
    assert context.market_data_connection_id == connection_id


def test_zerodha_with_explicit_market_data_connection(engine, monkeypatch):
    """Zerodha session should use explicit market_data_connection_id if provided."""
    SessionTesting = sessionmaker(bind=engine)
    store = DbTokenStore(session_factory=SessionTesting)
    session_manager = SessionManager(token_store=store, dev_mode=False)

    def fake_get_broker(broker_name, broker_user_id, config):
        return DummyBroker(broker_name, broker_user_id, config)

    monkeypatch.setattr("core.runtime.session_registry.BrokerFactory.get_broker", fake_get_broker)

    registry = SessionRegistry(
        session_factory=SessionTesting,
        session_manager=session_manager,
    )

    with SessionTesting() as session:
        user = models.User(email="test4@example.com", role="admin")
        session.add(user)
        session.flush()
        
        # Create primary Upstox (won't be used)
        primary_upstox = models.BrokerConnection(
            user_id=user.id,
            broker_name="upstox",
            broker_user_id="PRIMARY_USER",
            metadata_json=json.dumps({"api_key": "PRIMARY_UPSTOX"}),
        )
        session.add(primary_upstox)
        session.flush()
        
        # Create secondary Upstox (will be used as market data)
        secondary_upstox = models.BrokerConnection(
            user_id=user.id,
            broker_name="upstox",
            broker_user_id="SECONDARY_USER",
            metadata_json=json.dumps({"api_key": "SECONDARY_UPSTOX"}),
        )
        session.add(secondary_upstox)
        session.flush()
        
        # Create Zerodha connection for trading
        zerodha_connection = models.BrokerConnection(
            user_id=user.id,
            broker_name="zerodha",
            broker_user_id="ZERODHA_USER",
            metadata_json=json.dumps({"api_key": "KITE_KEY"}),
        )
        session.add(zerodha_connection)
        session.commit()
        zerodha_connection_id = zerodha_connection.id
        primary_upstox_id = primary_upstox.id
        secondary_upstox_id = secondary_upstox.id

    # Store tokens
    store.store_tokens(
        "upstox",
        {"access_token": "PRIMARY_TOKEN", "broker_user_id": "PRIMARY_USER"},
        connection_id=primary_upstox_id,
    )
    store.store_tokens(
        "upstox",
        {"access_token": "SECONDARY_TOKEN", "broker_user_id": "SECONDARY_USER"},
        connection_id=secondary_upstox_id,
    )
    store.store_tokens(
        "zerodha",
        {"access_token": "ZERODHA_TOKEN", "broker_user_id": "ZERODHA_USER"},
        connection_id=zerodha_connection_id,
    )

    # Provide explicit market_data_connection_id
    context = registry.create_session(
        broker_connection_id=zerodha_connection_id,
        market_data_connection_id=secondary_upstox_id,
    )
    
    assert context.market_data_connection_id == secondary_upstox_id
    # Primary should not be used since we explicitly provided secondary
