from __future__ import annotations

from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from core.services.broker_session_orchestrator import SessionReadiness


class SessionStartRequest(BaseModel):
    session_user_id: Optional[str] = Field(default=None, description="Broker login/user id")
    broker_name: Optional[str] = Field(default=None, description="Broker label (zerodha or upstox)")
    broker_config: Dict[str, str] = Field(default_factory=dict)
    broker_connection_id: Optional[int] = Field(
        default=None,
        description="Trading broker connection ID. For Zerodha, must also have Upstox connected for market data.",
    )
    market_data_connection_id: Optional[int] = Field(
        default=None,
        description="Market data provider connection ID (must be Upstox). If not provided for Zerodha trading, auto-selects active Upstox connection.",
    )
    warm_start: bool = False
    device_id: Optional[str] = Field(
        default=None, description="Device/session scope for this trading session"
    )


class SessionResponse(BaseModel):
    session_id: str
    broker_user_id: str
    user_id: Optional[str] = None
    broker: str
    expires_at: Optional[str] = None


class BrokerSessionBootstrapRequest(BaseModel):
    """Optional broker scope for automatic session readiness resolution."""

    broker_name: Optional[str] = None
    broker_connection_id: Optional[int] = None
    warm_start: bool = True
    refresh_data: bool = False


class BrokerAccountStatus(BaseModel):
    connection_id: int
    broker_name: str
    broker_user_id: Optional[str] = None
    token_status: str = "missing"
    expires_at: Optional[str] = None


class BrokerSessionBootstrapResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: SessionReadiness
    broker_connected: bool = False
    requires_selection: bool = False
    broker_name: Optional[str] = None
    connection_id: Optional[int] = None
    broker_user_id: Optional[str] = None
    session_id: Optional[str] = None
    session: Optional[dict] = None
    candidates: list[BrokerAccountStatus] = Field(default_factory=list)
    message: Optional[str] = None
    data_status: str = "unavailable"
