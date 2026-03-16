"""Authentication and user management service."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from api import config
from core.auth.context import UserContext
from core.security.jwt import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_token,
)
from core.security.passwords import PasswordError, hash_password, verify_password
from db import models
from db.database import SessionLocal


@dataclass
class LoginResult:
    access_token: str
    refresh_token: str
    user_id: int
    tenant_id: int
    email: str
    role: str
    trading_enabled: bool = False
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class AuthService:
    def __init__(self, session_factory=SessionLocal) -> None:
        self._session_factory = session_factory

    def register_user(
        self,
        *,
        email: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone: Optional[str] = None,
        role: str = "user",
    ) -> UserContext:
        with self._session_factory() as session:
            existing = session.query(models.User).filter(models.User.email == email.lower()).first()
            if existing:
                raise ValueError("Email already registered")
            
            tenant = session.query(models.Tenant).filter(models.Tenant.name == "DEFAULT").first()
            if not tenant:
                tenant = models.Tenant(name="DEFAULT")
                session.add(tenant)
                session.flush()
            
            user = models.User(
                tenant_id=tenant.id,
                email=email.lower(),
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                role=role,
            )
            session.add(user)
            session.flush()
            
            identity = models.UserIdentity(
                user_id=user.id,
                provider="password",
                password_hash=hash_password(password),
            )
            session.add(identity)
            session.commit()
            
            return UserContext(
                user_id=user.id,
                tenant_id=user.tenant_id,
                email=user.email,
                role=user.role,
            )

    def register_tenant(
        self,
        *,
        tenant_name: str,
        email: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone: Optional[str] = None,
        role: str = "admin",
    ) -> UserContext:
        with self._session_factory() as session:
            existing = session.query(models.User).filter(models.User.email == email.lower()).first()
            if existing:
                raise ValueError("Email already registered")
            
            tenant = models.Tenant(name=tenant_name)
            session.add(tenant)
            session.flush()
            
            user = models.User(
                tenant_id=tenant.id,
                email=email.lower(),
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                role=role,
            )
            session.add(user)
            session.flush()
            
            identity = models.UserIdentity(
                user_id=user.id,
                provider="password",
                password_hash=hash_password(password),
            )
            session.add(identity)
            session.commit()
            
            return UserContext(
                user_id=user.id,
                tenant_id=user.tenant_id,
                email=user.email,
                role=user.role,
            )

    def login(
        self,
        *,
        email: str,
        password: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> LoginResult:
        with self._session_factory() as session:
            user = session.query(models.User).filter(models.User.email == email.lower()).first()
            if not user:
                raise ValueError("Invalid email or password")
            
            identity = (
                session.query(models.UserIdentity)
                .filter(
                    models.UserIdentity.user_id == user.id,
                    models.UserIdentity.provider == "password",
                )
                .first()
            )
            
            if not identity or not identity.password_hash:
                raise ValueError("Invalid email or password")
            
            if not verify_password(password, identity.password_hash):
                raise ValueError("Invalid email or password")
            
            access_token = create_access_token({
                "sub": str(user.id),
                "tenant_id": user.tenant_id,
                "role": user.role,
            })
            
            refresh_token_str = create_refresh_token({"sub": str(user.id)})
            
            token_hash = hash_token(refresh_token_str)
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=config.REFRESH_TOKEN_EXPIRES_SECONDS)
            
            refresh_token = models.RefreshToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=expires_at,
                user_agent=user_agent,
                ip_address=ip_address,
            )
            session.add(refresh_token)
            session.commit()
            
            return LoginResult(
                access_token=access_token,
                refresh_token=refresh_token_str,
                user_id=user.id,
                tenant_id=user.tenant_id,
                email=user.email,
                role=user.role,
                trading_enabled=user.trading_enabled,
                first_name=user.first_name,
                last_name=user.last_name,
            )

    def refresh(
        self,
        refresh_token: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> LoginResult:
        with self._session_factory() as session:
            try:
                payload = decode_refresh_token(refresh_token)
            except TokenError:
                raise ValueError("Invalid or expired refresh token")
            
            user_id = int(payload.get("sub"))
            token_hash = hash_token(refresh_token)
            
            token_record = (
                session.query(models.RefreshToken)
                .filter(
                    models.RefreshToken.user_id == user_id,
                    models.RefreshToken.token_hash == token_hash,
                )
                .first()
            )
            
            if not token_record:
                raise ValueError("Invalid refresh token")
            
            if token_record.revoked_at:
                raise ValueError("Refresh token has been revoked")
            
            if token_record.expires_at < datetime.now(timezone.utc):
                raise ValueError("Refresh token has expired")
            
            user = session.get(models.User, user_id)
            if not user:
                raise ValueError("User not found")
            
            access_token = create_access_token({
                "sub": str(user.id),
                "tenant_id": user.tenant_id,
                "role": user.role,
            })
            
            new_refresh_token_str = create_refresh_token({"sub": str(user.id)})
            new_token_hash = hash_token(new_refresh_token_str)
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=config.REFRESH_TOKEN_EXPIRES_SECONDS)
            
            new_refresh_token = models.RefreshToken(
                user_id=user.id,
                token_hash=new_token_hash,
                expires_at=expires_at,
                user_agent=user_agent,
                ip_address=ip_address,
            )
            session.add(new_refresh_token)
            
            token_record.revoked_at = datetime.now(timezone.utc)
            session.commit()
            
            return LoginResult(
                access_token=access_token,
                refresh_token=new_refresh_token_str,
                user_id=user.id,
                tenant_id=user.tenant_id,
                email=user.email,
                role=user.role,
                trading_enabled=user.trading_enabled,
                first_name=user.first_name,
                last_name=user.last_name,
            )

    def logout(self, refresh_token: str) -> None:
        with self._session_factory() as session:
            try:
                payload = decode_refresh_token(refresh_token)
            except TokenError:
                return
            
            user_id = int(payload.get("sub"))
            token_hash = hash_token(refresh_token)
            
            token_record = (
                session.query(models.RefreshToken)
                .filter(
                    models.RefreshToken.user_id == user_id,
                    models.RefreshToken.token_hash == token_hash,
                )
                .first()
            )
            
            if token_record and not token_record.revoked_at:
                token_record.revoked_at = datetime.now(timezone.utc)
                session.commit()

    def revoke_all_user_tokens(self, user_id: int) -> None:
        with self._session_factory() as session:
            session.query(models.RefreshToken).filter(
                models.RefreshToken.user_id == user_id,
                models.RefreshToken.revoked_at.is_(None),
            ).update({"revoked_at": datetime.now(timezone.utc)})
            session.commit()

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
        return UserContext(
            user_id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            role=role,
            trading_enabled=user.trading_enabled,
        )

    def get_user_broker_connections(self, user_id: int) -> list[Dict[str, Any]]:
        with self._session_factory() as session:
            connections = (
                session.query(models.BrokerConnection)
                .filter(models.BrokerConnection.user_id == user_id)
                .all()
            )
            return [
                {
                    "id": c.id,
                    "broker_name": c.broker_name,
                    "broker_user_id": c.broker_user_id,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                    "token_updated_at": c.token_updated_at.isoformat() if c.token_updated_at else None,
                }
                for c in connections
            ]

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
                    role="admin",
                    trading_enabled=True,
                )
                session.add(user)
                session.commit()
            return UserContext(
                user_id=user.id,
                tenant_id=tenant.id,
                email=user.email,
                role=user.role,
                is_dev=True,
                trading_enabled=user.trading_enabled,
            )

    def bootstrap_admin(self, admin_email: str) -> Optional[UserContext]:
        """Bootstrap admin user from BOOTSTRAP_ADMIN_EMAIL env var."""
        if not admin_email:
            return None
        
        with self._session_factory() as session:
            # Check if any admin exists
            admin_exists = session.query(models.User).filter(models.User.role == "admin").first()
            if admin_exists:
                import logging
                logging.getLogger("tradecraftx.auth").info("Admin bootstrap skipped - admin already exists")
                return None
            
            # Find user with the bootstrap email
            user = session.query(models.User).filter(models.User.email == admin_email.lower()).first()
            if not user:
                import logging
                logging.getLogger("tradecraftx.auth").info(f"Admin bootstrap skipped - user {admin_email} not found")
                return None
            
            # Promote to admin
            user.role = "admin"
            session.commit()
            
            import logging
            logging.getLogger("tradecraftx.auth").info(f"Admin bootstrap completed - {admin_email} promoted to admin")
            
            return UserContext(user_id=user.id, tenant_id=user.tenant_id, email=user.email, role=user.role)

    def set_user_trading_enabled(self, user_id: int, enabled: bool, admin_user_id: int) -> models.User:
        """Enable or disable trading for a user. Admin action."""
        with self._session_factory() as session:
            user = session.get(models.User, user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            user.trading_enabled = enabled
            session.commit()
            
            # TODO: Add audit log entry here when audit table is implemented
            import logging
            logging.getLogger("tradecraftx.auth").info(
                f"Admin action: user {user_id} trading_enabled set to {enabled} by admin {admin_user_id}"
            )
            
            return user

    def get_user_by_id(self, user_id: int) -> Optional[models.User]:
        with self._session_factory() as session:
            return session.get(models.User, user_id)
