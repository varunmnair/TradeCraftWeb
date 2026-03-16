"""JWT helpers."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from jose import JWTError, jwt

from api import config


class TokenError(Exception):
    pass


def create_access_token(data: Dict[str, Any], expires_seconds: int | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(seconds=expires_seconds or config.ACCESS_TOKEN_EXPIRES_SECONDS)
    to_encode = {**data, "exp": expire, "type": "access"}
    return jwt.encode(to_encode, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise TokenError("Invalid token type")
        return payload
    except JWTError as exc:
        raise TokenError(str(exc)) from exc


def create_refresh_token(data: Dict[str, Any]) -> str:
    expire = datetime.now(timezone.utc) + timedelta(seconds=config.REFRESH_TOKEN_EXPIRES_SECONDS)
    to_encode = {**data, "exp": expire, "type": "refresh"}
    return jwt.encode(to_encode, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def decode_refresh_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise TokenError("Invalid token type")
        return payload
    except JWTError as exc:
        raise TokenError(str(exc)) from exc


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def verify_token_hash(token: str, token_hash: str) -> bool:
    return secrets.compare_digest(hash_token(token), token_hash)
