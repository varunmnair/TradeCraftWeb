"""Password hashing helpers."""

from passlib.context import CryptContext


_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# bcrypt has a 72-byte limit
MAX_PASSWORD_LENGTH = 72


def hash_password(password: str) -> str:
    # Truncate password to 72 bytes (bcrypt limit)
    truncated = password[:MAX_PASSWORD_LENGTH].encode('utf-8')[:MAX_PASSWORD_LENGTH].decode('utf-8', errors='ignore')
    return _pwd_context.hash(truncated)


def verify_password(password: str, hashed: str) -> bool:
    if not hashed:
        return False
    # Truncate password to 72 bytes for verification
    truncated = password[:MAX_PASSWORD_LENGTH].encode('utf-8')[:MAX_PASSWORD_LENGTH].decode('utf-8', errors='ignore')
    return _pwd_context.verify(truncated, hashed)
