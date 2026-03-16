"""Tests for authentication flow."""

import pytest
from datetime import datetime, timedelta, timezone

from core.security.passwords import hash_password, verify_password, PasswordError
from core.security.jwt import (
    create_access_token,
    decode_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_token,
    TokenError,
)


class TestPasswordHashing:
    def test_hash_password_creates_hash(self):
        password = "securepassword123"
        hashed = hash_password(password)
        assert hashed != password
        assert hashed.startswith("$argon2")

    def test_verify_password_correct(self):
        password = "securepassword123"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        password = "securepassword123"
        wrong_password = "wrongpassword"
        hashed = hash_password(password)
        assert verify_password(wrong_password, hashed) is False

    def test_verify_password_empty(self):
        assert verify_password("", "anyhash") is False

    def test_verify_password_none_hash(self):
        assert verify_password("password", None) is False

    def test_password_too_short(self):
        with pytest.raises(PasswordError) as exc:
            hash_password("short")
        assert "at least 10 characters" in str(exc.value)

    def test_password_minimum_length(self):
        password = "1234567890"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True


class TestJWTTokens:
    def test_create_access_token(self):
        token = create_access_token({"sub": "1", "tenant_id": 1, "role": "admin"})
        assert token is not None
        assert isinstance(token, str)

    def test_decode_access_token(self):
        data = {"sub": "1", "tenant_id": 1, "role": "admin"}
        token = create_access_token(data)
        decoded = decode_access_token(token)
        assert decoded["sub"] == "1"
        assert decoded["tenant_id"] == 1
        assert decoded["role"] == "admin"
        assert decoded["type"] == "access"

    def test_decode_invalid_token(self):
        with pytest.raises(TokenError):
            decode_access_token("invalid.token.here")

    def test_create_refresh_token(self):
        token = create_refresh_token({"sub": "1"})
        assert token is not None
        assert isinstance(token, str)

    def test_decode_refresh_token(self):
        token = create_refresh_token({"sub": "1"})
        decoded = decode_refresh_token(token)
        assert decoded["sub"] == "1"
        assert decoded["type"] == "refresh"

    def test_decode_wrong_token_type(self):
        access_token = create_access_token({"sub": "1"})
        with pytest.raises(TokenError) as exc:
            decode_refresh_token(access_token)
        assert "Invalid token type" in str(exc.value)


class TestTokenHashing:
    def test_hash_token(self):
        token = "some-refresh-token"
        hashed = hash_token(token)
        assert hashed != token
        assert len(hashed) == 64  # SHA256 hex

    def test_hash_token_consistency(self):
        token = "some-refresh-token"
        assert hash_token(token) == hash_token(token)
