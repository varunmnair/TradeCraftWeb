from __future__ import annotations

from typing import Dict, Optional

from pydantic import BaseModel, Field


class SessionStartRequest(BaseModel):
    session_user_id: Optional[str] = Field(
        default=None, description="Broker login/user id"
    )
    broker_name: Optional[str] = Field(
        default=None, description="Broker label (zerodha or upstox)"
    )
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


class SessionResponse(BaseModel):
    session_id: str
    broker_user_id: str
    user_id: Optional[str] = None
    broker: str
    expires_at: Optional[str] = None
