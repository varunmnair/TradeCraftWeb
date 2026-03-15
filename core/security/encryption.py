"""Token encryption helper."""

from __future__ import annotations

import base64
import json
import os
from functools import lru_cache
from typing import Any, Dict

from cryptography.fernet import Fernet


class TokenEncryptor:
    def __init__(self, key: str | None = None) -> None:
        env_key = key or os.getenv("TOKEN_ENCRYPTION_KEY")
        if not env_key:
            allow_insecure = os.getenv("ALLOW_INSECURE_TOKENS", "1") == "1"
            if not allow_insecure:
                raise RuntimeError("TOKEN_ENCRYPTION_KEY not configured")
            env_key = base64.urlsafe_b64encode(b"tradecraftx-dev-key".ljust(32, b"0")).decode()
        if len(env_key) != 44:
            env_key = base64.urlsafe_b64encode(env_key.encode().ljust(32, b"0")).decode()
        self._fernet = Fernet(env_key)

    def encrypt_dict(self, data: Dict[str, Any]) -> bytes:
        payload = json.dumps(data).encode()
        return self._fernet.encrypt(payload)

    def decrypt_dict(self, blob: bytes | None) -> Dict[str, Any]:
        if not blob:
            return {}
        data = self._fernet.decrypt(blob)
        return json.loads(data.decode())


@lru_cache(maxsize=1)
def get_encryptor() -> TokenEncryptor:
    return TokenEncryptor()
