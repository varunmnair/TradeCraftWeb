from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    display_name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
