from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.main import create_app
from api.dependencies import (
    get_auth_service,
    get_broker_connection_service,
    get_broker_auth_state_service,
    get_db_session,
    get_job_runner,
    get_session_manager,
    get_session_registry,
)
from core.runtime.job_runner import JobRunner
from core.runtime.session_registry import SessionRegistry
from core.session_manager import SessionManager
from core.session_tokens import DbTokenStore
from core.services.auth_service import AuthService
from core.services.broker_auth_service import BrokerAuthStateService
from core.services.broker_connection_service import BrokerConnectionService
from db.database import Base
from db import models  # noqa: F401 - ensures models are registered


TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def engine():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    SessionTesting = sessionmaker(bind=connection)
    session = SessionTesting()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session):
    app = create_app()
    bind = db_session.get_bind()
    SessionTesting = sessionmaker(bind=bind)
    token_store = DbTokenStore(session_factory=SessionTesting)
    session_manager = SessionManager(token_store=token_store)
    session_registry = SessionRegistry(session_factory=SessionTesting, session_manager=session_manager)
    broker_service = BrokerConnectionService(session_factory=SessionTesting)
    auth_state_service = BrokerAuthStateService(session_factory=SessionTesting)
    auth_service = AuthService(session_factory=SessionTesting)
    job_runner = JobRunner(session_factory=SessionTesting, session_registry=session_registry)

    def _override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_session_manager] = lambda: session_manager
    app.dependency_overrides[get_session_registry] = lambda: session_registry
    app.dependency_overrides[get_broker_connection_service] = lambda: broker_service
    app.dependency_overrides[get_broker_auth_state_service] = lambda: auth_state_service
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_job_runner] = lambda: job_runner
    app.state.test_auth_state_service = auth_state_service
    return TestClient(app)
