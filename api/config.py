"""Centralized configuration for TradeCraftX.

This module provides a single source of truth for all application configuration.
The APP_MODE environment variable controls behavior without changing core logic.
"""

from __future__ import annotations

import os
from typing import Any

# Load dotenv early
from dotenv import load_dotenv

load_dotenv()


class ConfigError(Exception):
    """Raised when required configuration is missing in production mode."""
    pass


def _get_env(key: str, default: str | None = None) -> str | None:
    """Get environment variable, returning default if not set."""
    return os.getenv(key, default)


def _get_bool_env(key: str, default: bool = False) -> bool:
    """Get boolean environment variable."""
    return _get_env(key, str(default)).lower() in ("1", "true", "yes")


# ============================================================================
# APP MODE - Primary Switch
# ============================================================================

APP_MODE = _get_env("APP_MODE", "dev").lower()
IS_DEV = APP_MODE == "dev"
IS_PROD = APP_MODE == "prod"

# Legacy support - these still work but are not required
# DEV_MODE and HOSTED_MODE can override for backward compatibility
_LEGACY_DEV_MODE = _get_bool_env("DEV_MODE", True)
_LEGACY_HOSTED_MODE = _get_bool_env("HOSTED_MODE", False)

# For now, allow legacy env vars to influence behavior if explicitly set
# This maintains backward compatibility
if "DEV_MODE" in os.environ:
    IS_DEV = _LEGACY_DEV_MODE
    IS_PROD = not _LEGACY_DEV_MODE
if "HOSTED_MODE" in os.environ:
    # HOSTED_MODE=1 implies prod mode
    if _LEGACY_HOSTED_MODE:
        IS_PROD = True
        IS_DEV = False

# ============================================================================
# Security Configuration
# ============================================================================

JWT_SECRET = _get_env("JWT_SECRET", "dev-secret-key" if IS_DEV else None)
JWT_ALGORITHM = _get_env("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRES_SECONDS = int(_get_env("ACCESS_TOKEN_EXPIRES", "900"))
REFRESH_TOKEN_EXPIRES_SECONDS = int(_get_env("REFRESH_TOKEN_EXPIRES", "604800"))  # 7 days

# Cookie settings
REFRESH_TOKEN_COOKIE_NAME = "refresh_token"
REFRESH_TOKEN_COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 days in seconds

# Cookie security - Secure in prod, SameSite=Lax by default
COOKIE_SECURE = IS_PROD
COOKIE_SAMESITE = "lax" if not _get_env("COOKIE_SAMESITE") else _get_env("COOKIE_SAMESITE")

# Token encryption - required in prod
TOKEN_ENCRYPTION_KEY = _get_env("TOKEN_ENCRYPTION_KEY")
ALLOW_INSECURE_TOKENS = _get_bool_env("ALLOW_INSECURE_TOKENS", IS_DEV)

# Validate production requirements
if IS_PROD:
    if not JWT_SECRET or JWT_SECRET == "dev-secret-key":
        raise ConfigError("JWT_SECRET must be set in production")
    if not TOKEN_ENCRYPTION_KEY and not ALLOW_INSECURE_TOKENS:
        raise ConfigError(
            "TOKEN_ENCRYPTION_KEY must be set in production, "
            "or set ALLOW_INSECURE_TOKENS=1 for development"
        )

# ============================================================================
# Database Configuration
# ============================================================================

DATABASE_URL = _get_env("DATABASE_URL")

if IS_PROD and not DATABASE_URL:
    raise ConfigError("DATABASE_URL must be set in production")

# ============================================================================
# Broker API Keys
# ============================================================================

# Zerodha
KITE_API_KEY = _get_env("KITE_API_KEY")
KITE_API_SECRET = _get_env("KITE_API_SECRET")
KITE_REDIRECT_URI = _get_env("KITE_REDIRECT_URI", "http://localhost:8000/brokers/zerodha/callback")

# Upstox
UPSTOX_API_KEY = _get_env("UPSTOX_API_KEY")
UPSTOX_API_SECRET = _get_env("UPSTOX_API_SECRET")
UPSTOX_REDIRECT_URI = _get_env("UPSTOX_REDIRECT_URI", "http://localhost:8000/brokers/upstox/callback")

# ============================================================================
# AI Provider Keys (Optional)
# ============================================================================

GEMINI_API_KEY = _get_env("GEMINI_API_KEY")
GROQ_API_KEY = _get_env("GROQ_API_KEY")

# ============================================================================
# Admin Bootstrap
# ============================================================================

BOOTSTRAP_ADMIN_EMAIL = _get_env("BOOTSTRAP_ADMIN_EMAIL")

# ============================================================================
# Logging Configuration
# ============================================================================

LOG_LEVEL = _get_env("LOG_LEVEL", "DEBUG" if IS_DEV else "INFO")

# ============================================================================
# CORS Configuration
# ============================================================================

# In prod, be more restrictive with CORS
CORS_ALLOWED_ORIGINS = _get_env("CORS_ALLOWED_ORIGINS")
# Default: allow all in dev, restrict in prod
if IS_PROD and not CORS_ALLOWED_ORIGINS:
    CORS_ALLOWED_ORIGINS = ""  # Empty means no CORS - will be handled below
elif not CORS_ALLOWED_ORIGINS:
    CORS_ALLOWED_ORIGINS = "*"

# ============================================================================
# Error Handling
# ============================================================================

# Show detailed errors in dev, sanitize in prod
SHOW_DETAILED_ERRORS = IS_DEV


def get_cors_config() -> dict[str, Any]:
    """Get CORS configuration based on APP_MODE."""
    if IS_PROD and CORS_ALLOWED_ORIGINS:
        origins = [o.strip() for o in CORS_ALLOWED_ORIGINS.split(",") if o.strip()]
    elif IS_PROD:
        origins = []  # No CORS in prod unless explicitly configured
    else:
        # In dev, allow both localhost:5173 (vite) and localhost:3000 (react)
        origins = ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173", "http://127.0.0.1:3000"]
    
    return {
        "allow_origins": origins,
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }


def get_error_detail(exc: Exception) -> str:
    """Get error detail based on APP_MODE."""
    if SHOW_DETAILED_ERRORS:
        return str(exc)
    # In prod, return sanitized message
    return "An internal error occurred"
