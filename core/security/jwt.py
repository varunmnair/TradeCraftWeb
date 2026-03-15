"""JWT helpers."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from jose import JWTError, jwt


JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-key")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRES_SECONDS = int(os.getenv("ACCESS_TOKEN_EXPIRES", "900"))


class TokenError(Exception):
    pass


def create_access_token(data: Dict[str, Any], expires_seconds: int | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(seconds=expires_seconds or ACCESS_TOKEN_EXPIRES_SECONDS)
    to_encode = {**data, "exp": expire}
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise TokenError(str(exc)) from exc
