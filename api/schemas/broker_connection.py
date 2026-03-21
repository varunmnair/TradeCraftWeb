from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field


class BrokerConnectionCreate(BaseModel):
    broker_name: str = Field(examples=["zerodha", "upstox"])
    tokens: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    user_id: int | None = None


class BrokerConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    broker_name: str
    created_at: datetime
