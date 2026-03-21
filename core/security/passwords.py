"""Password hashing helpers using Argon2id."""

from __future__ import annotations

from passlib.context import CryptContext

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128

_pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


class PasswordError(Exception):
    """Raised for password validation errors."""

    pass


def _validate_password(password: str) -> None:
    """Validate password meets basic requirements."""
    if not password:
        raise PasswordError("Password cannot be empty")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long"
        )
    if len(password) > MAX_PASSWORD_LENGTH:
        raise PasswordError(
            f"Password must not exceed {MAX_PASSWORD_LENGTH} characters"
        )


def hash_password(password: str) -> str:
    """Hash a password using Argon2id."""
    _validate_password(password)
    return _pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a hash."""
    if not password or not hashed:
        return False
    try:
        return _pwd_context.verify(password, hashed)
    except Exception:
        return False
