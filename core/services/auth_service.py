"""Authentication and user management service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from core.auth.context import UserContext
from core.security.jwt import TokenError, create_access_token, decode_access_token
from core.security.passwords import hash_password, verify_password
from db import models
from db.database import SessionLocal


DEV_MODE = os.getenv("DEV_MODE", "1") == "1"


class AuthService:
    def __init__(self, session_factory=SessionLocal) -> None:
        self._session_factory = session_factory

    def register_tenant(self, *, tenant_name: str, email: str, password: str, role: str = "admin") -> UserContext:
        with self._session_factory() as session:
            tenant = models.Tenant(name=tenant_name)
            session.add(tenant)
            session.flush()
            user = models.User(
                tenant_id=tenant.id,
                email=email.lower(),
                hashed_password=hash_password(password),
                role=role,
            )
            session.add(user)
            session.commit()
            return UserContext(user_id=user.id, tenant_id=tenant.id, email=user.email, role=user.role)

    def create_user(self, *, tenant_id: int, email: str, password: str, role: str = "user") -> UserContext:
        with self._session_factory() as session:
            user = models.User(
                tenant_id=tenant_id,
                email=email.lower(),
                hashed_password=hash_password(password),
                role=role,
            )
            session.add(user)
            session.commit()
            return UserContext(user_id=user.id, tenant_id=tenant_id, email=user.email, role=user.role)

    def login(self, *, email: str, password: str) -> dict:
        with self._session_factory() as session:
            user = session.query(models.User).filter(models.User.email == email.lower()).first()
            if not user or not verify_password(password, user.hashed_password):
                raise ValueError("Invalid credentials")
            token = create_access_token({"sub": str(user.id), "tenant_id": user.tenant_id, "role": user.role})
            return {
                "access_token": token,
                "token_type": "bearer",
                "user": {
                    "id": user.id,
                    "tenant_id": user.tenant_id,
                    "email": user.email,
                    "role": user.role,
                },
            }

    def get_user(self, user_id: int) -> Optional[models.User]:
        with self._session_factory() as session:
            return session.get(models.User, user_id)

    def decode_token(self, token: str) -> UserContext:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub"))
        tenant_id = payload.get("tenant_id")
        role = payload.get("role", "user")
        user = self.get_user(user_id)
        if not user:
            raise TokenError("User not found")
        if tenant_id != user.tenant_id:
            raise TokenError("Tenant mismatch")
        return UserContext(user_id=user.id, tenant_id=user.tenant_id, email=user.email, role=role)

    def ensure_dev_user(self) -> UserContext:
        with self._session_factory() as session:
            tenant = session.query(models.Tenant).filter(models.Tenant.name == "DEV").first()
            if not tenant:
                tenant = models.Tenant(name="DEV")
                session.add(tenant)
                session.flush()
            user = session.query(models.User).filter(models.User.email == "dev@tradecraftx.local").first()
            if not user:
                user = models.User(
                    tenant_id=tenant.id,
                    email="dev@tradecraftx.local",
                    hashed_password="disabled",
                    role="admin",
                )
                session.add(user)
                session.commit()
            return UserContext(user_id=user.id, tenant_id=tenant.id, email=user.email, role=user.role, is_dev=True)
