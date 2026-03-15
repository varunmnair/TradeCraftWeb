from __future__ import annotations

from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    tenant_name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthUser(BaseModel):
    id: int
    tenant_id: int
    email: EmailStr
    role: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user: AuthUser


class MeResponse(AuthUser):
    pass
