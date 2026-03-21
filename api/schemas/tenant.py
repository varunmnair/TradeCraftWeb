from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TenantCreate(BaseModel):
    name: str


class TenantResponse(BaseModel):
    id: int
    name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
