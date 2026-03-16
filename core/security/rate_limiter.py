"""Simple in-memory rate limiter for auth endpoints."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Tuple

from api import config


@dataclass
class RateLimitConfig:
    max_attempts: int
    window_seconds: int
    lockout_seconds: int


class RateLimiter:
    def __init__(self) -> None:
        self._attempts: Dict[str, list] = defaultdict(list)
        self._lockouts: Dict[str, float] = {}
        
        # More lenient in dev mode
        if config.IS_DEV:
            self.register_config = RateLimitConfig(
                max_attempts=20,
                window_seconds=300,
                lockout_seconds=30,
            )
            self.login_config = RateLimitConfig(
                max_attempts=20,
                window_seconds=300,
                lockout_seconds=30,
            )
            self.refresh_config = RateLimitConfig(
                max_attempts=50,
                window_seconds=300,
                lockout_seconds=10,
            )
        else:
            self.register_config = RateLimitConfig(
                max_attempts=5,
                window_seconds=300,
                lockout_seconds=300,
            )
            self.login_config = RateLimitConfig(
                max_attempts=5,
                window_seconds=300,
                lockout_seconds=300,
            )
            self.refresh_config = RateLimitConfig(
                max_attempts=10,
                window_seconds=300,
                lockout_seconds=60,
            )
    
    def _get_client_id(self, request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
    
    def _cleanup_old_attempts(self, key: str, window_seconds: int) -> None:
        cutoff = time.time() - window_seconds
        self._attempts[key] = [t for t in self._attempts[key] if t > cutoff]
    
    def check_rate_limit(self, request, endpoint: str) -> Tuple[bool, str]:
        client_id = self._get_client_id(request)
        key = f"{endpoint}:{client_id}"
        
        if key in self._lockouts:
            lockout_until = self._lockouts[key]
            if time.time() < lockout_until:
                remaining = int(lockout_until - time.time())
                return False, f"Too many attempts. Try again in {remaining} seconds"
            else:
                del self._lockouts[key]
        
        if endpoint == "register":
            config_obj = self.register_config
        elif endpoint == "login":
            config_obj = self.login_config
        elif endpoint == "refresh":
            config_obj = self.refresh_config
        else:
            config_obj = self.register_config
        
        self._cleanup_old_attempts(key, config_obj.window_seconds)
        
        if len(self._attempts[key]) >= config_obj.max_attempts:
            self._lockouts[key] = time.time() + config_obj.lockout_seconds
            self._attempts[key] = []
            return False, f"Rate limit exceeded. Try again in {config_obj.lockout_seconds} seconds"
        
        self._attempts[key].append(time.time())
        return True, ""
    
    def record_success(self, request, endpoint: str) -> None:
        client_id = self._get_client_id(request)
        key = f"{endpoint}:{client_id}"
        self._attempts[key] = []
        if key in self._lockouts:
            del self._lockouts[key]


_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
