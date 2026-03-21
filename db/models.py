"""SQLAlchemy models for TradeCraftX."""

from __future__ import annotations

from datetime import datetime
import json

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, func, Index, UniqueConstraint
from sqlalchemy.orm import relationship

from db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False, unique=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    role = Column(String(32), nullable=False, default="user")
    trading_enabled = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    broker_connections = relationship("BrokerConnection", back_populates="user", cascade="all, delete-orphan")
    identities = relationship("UserIdentity", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")


class UserIdentity(Base):
    __tablename__ = "user_identities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    provider = Column(String(50), nullable=False, default="password")
    password_hash = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="identities")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)

    user = relationship("User", back_populates="refresh_tokens")


class BrokerConnection(Base):
    __tablename__ = "broker_connections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    broker_name = Column(String(50), nullable=False)
    broker_user_id = Column(String(255), nullable=True)
    encrypted_tokens = Column(LargeBinary, nullable=True)
    metadata_json = Column(Text, nullable=True)
    token_updated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="broker_connections")

    __table_args__ = (
        UniqueConstraint("user_id", "broker_name", "broker_user_id", name="uq_user_broker_broker_user_id"),
    )

    def metadata_dict(self):
        try:
            return json.loads(self.metadata_json or "{}")
        except json.JSONDecodeError:
            return {}


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
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
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(255), nullable=False)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(String(255), nullable=True)
    broker_connection_id = Column(Integer, ForeignKey("broker_connections.id"), nullable=True)
    metadata_json = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    request_id = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class BrokerAuthState(Base):
    __tablename__ = "broker_auth_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    connection_id = Column(Integer, ForeignKey("broker_connections.id"), nullable=False)
    broker_name = Column(String(50), nullable=False)
    state_token = Column(String(255), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EntryStrategy(Base):
    __tablename__ = "entry_strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    symbol = Column(String(50), nullable=False, index=True)
    broker = Column(String(20), nullable=True)
    broker_user_id = Column(String(50), nullable=True)
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
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    symbols_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EntryStrategyVersion(Base):
    __tablename__ = "entry_strategy_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
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


class MarketUniverse(Base):
    __tablename__ = "market_universe"

    symbol = Column(String(50), primary_key=True)
    enabled = Column(Boolean, nullable=False, default=True)
    universe = Column(String(50), nullable=False, default="NIFTY500")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MarketQuoteDaily(Base):
    __tablename__ = "market_quotes_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(50), nullable=False)
    trade_date = Column(String(10), nullable=False)
    cmp = Column(Float, nullable=True)
    as_of_ts = Column(DateTime(timezone=True), nullable=True)
    source = Column(String(20), nullable=True)

    __table_args__ = (
        UniqueConstraint("symbol", "trade_date", name="uq_symbol_trade_date"),
    )


class MarketCandleDaily(Base):
    __tablename__ = "market_candles_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(50), nullable=False)
    trade_date = Column(String(10), nullable=False)
    open = Column(Float, nullable=True)
    high = Column(Float, nullable=True)
    low = Column(Float, nullable=True)
    close = Column(Float, nullable=True)
    volume = Column(Integer, nullable=True)
    source = Column(String(20), nullable=True)

    __table_args__ = (
        UniqueConstraint("symbol", "trade_date", name="uq_candle_symbol_trade_date"),
    )


class SymbolCatalog(Base):
    __tablename__ = "symbol_catalog"

    symbol = Column(String(50), primary_key=True)
    company_name = Column(String(255), nullable=False)
    series = Column(String(10), nullable=False)
    isin = Column(String(20), nullable=False)
    exchange = Column(String(10), nullable=False, default="NSE")
    cmp = Column(Float, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class OhlcvDaily(Base):
    __tablename__ = "ohlcv_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(50), nullable=False)
    trade_date = Column(Date, nullable=False)
    open = Column(Float, nullable=True)
    high = Column(Float, nullable=True)
    low = Column(Float, nullable=True)
    close = Column(Float, nullable=True)
    volume = Column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("symbol", "trade_date", name="uq_ohlcv_symbol_trade_date"),
        Index("ix_ohlcv_symbol_trade_date", "symbol", trade_date.desc()),
    )


class UserTrade(Base):
    __tablename__ = "user_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    session_id = Column(String(36), nullable=True, index=True)  # Session-scoped trades
    broker = Column(String(20), nullable=False)
    symbol = Column(String(50), nullable=False, index=True)
    isin = Column(String(50), nullable=True)
    trade_date = Column(String(10), nullable=False, index=True)
    exchange = Column(String(10), nullable=True)
    segment = Column(String(10), nullable=True)
    series = Column(String(10), nullable=True)
    side = Column(String(10), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    trade_id = Column(String(50), nullable=True)
    order_id = Column(String(50), nullable=True)
    order_execution_time = Column(String(50), nullable=True)
    source = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "broker", "trade_id", name="uq_user_broker_trade_id"),
        Index("ix_trades_session_symbol", "session_id", "symbol"),
    )
