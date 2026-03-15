"""SQLAlchemy models for multi-tenant runtime."""

from __future__ import annotations

from datetime import datetime
import json

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.orm import relationship

from db.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    hashed_password = Column(String(255), nullable=False, default="disabled")
    role = Column(String(32), nullable=False, default="user")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    tenant = relationship("Tenant", back_populates="users")
    broker_connections = relationship("BrokerConnection", back_populates="user", cascade="all, delete-orphan")


class BrokerConnection(Base):
    __tablename__ = "broker_connections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    broker_name = Column(String(50), nullable=False)
    broker_user_id = Column(String(255), nullable=True)
    encrypted_tokens = Column(LargeBinary, nullable=True)
    metadata_json = Column(Text, nullable=True)
    token_updated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="broker_connections")

    def metadata_dict(self):
        try:
            return json.loads(self.metadata_json or "{}")
        except json.JSONDecodeError:
            return {}


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id = Column(String(255), nullable=False)
    job_type = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    progress = Column(Float, nullable=False, default=0.0)
    log = Column(Text, nullable=True)
    payload_json = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)
    error_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(255), nullable=False)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(String(255), nullable=True)
    request_json = Column(Text, nullable=True)
    response_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class BrokerAuthState(Base):
    __tablename__ = "broker_auth_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    connection_id = Column(Integer, ForeignKey("broker_connections.id"), nullable=False)
    broker_name = Column(String(50), nullable=False)
    state_token = Column(String(255), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EntryStrategy(Base):
    __tablename__ = "entry_strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    symbol = Column(String(50), nullable=False, index=True)
    broker = Column(String(20), nullable=True)  # 'upstox' or 'zerodha'
    broker_user_id = Column(String(50), nullable=True)  # e.g., '32ADGT' or 'NM9165'
    allocated = Column(Float, nullable=True)
    quality = Column(String(50), nullable=True)
    exchange = Column(String(10), nullable=True)
    dynamic_averaging_enabled = Column(Boolean, default=False, nullable=False)
    averaging_rules_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    levels = relationship("EntryLevel", back_populates="strategy", cascade="all, delete-orphan")

    __table_args__ = (
        {"mysql_charset": "utf8mb4", "mysql_engine": "InnoDB"},
    )


class EntryLevel(Base):
    __tablename__ = "entry_levels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(Integer, ForeignKey("entry_strategies.id"), nullable=False)
    level_no = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    strategy = relationship("EntryStrategy", back_populates="levels")

    __table_args__ = (
        {"mysql_charset": "utf8mb4", "mysql_engine": "InnoDB"},
    )


class EntryStrategyUpload(Base):
    __tablename__ = "entry_strategy_uploads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    symbols_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EntryStrategyVersion(Base):
    __tablename__ = "entry_strategy_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    strategy_id = Column(Integer, ForeignKey("entry_strategies.id"), nullable=False)
    version_no = Column(Integer, nullable=False)
    action = Column(String(50), nullable=False)
    levels_snapshot_json = Column(Text, nullable=False)
    changes_summary = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        {"mysql_charset": "utf8mb4", "mysql_engine": "InnoDB"},
    )
