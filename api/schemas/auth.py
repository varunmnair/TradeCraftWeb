from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    pass


class AuthUser(BaseModel):
    id: int
    tenant_id: int
    email: EmailStr
    role: str
    trading_enabled: bool = False
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user: AuthUser


class MeResponse(AuthUser):
    broker_connections: list[dict] = []


class BrokerConnectionSummary(BaseModel):
    id: int
    broker_name: str
    broker_user_id: Optional[str]
    created_at: Optional[str]
    token_updated_at: Optional[str]
