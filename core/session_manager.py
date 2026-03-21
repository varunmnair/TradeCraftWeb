"""SessionManager that chooses proper token store (file for dev, DB for SaaS)."""

from __future__ import annotations

import os
from typing import Optional

from core.session_tokens import (
    BaseTokenStore,
    DbTokenStore,
    FileTokenStore,
    TokenBundle,
)


class SessionManager:
    def __init__(
        self,
        *,
        token_store: BaseTokenStore | None = None,
        dev_mode: bool = True,
    ) -> None:
        self.dev_mode = dev_mode
        self.token_store = token_store or (
            FileTokenStore() if dev_mode else DbTokenStore()
        )

        self.kite_api_key = os.getenv("KITE_API_KEY")
        self.kite_api_secret = os.getenv("KITE_API_SECRET")
        self.upstox_api_key = os.getenv("UPSTOX_API_KEY")
        self.upstox_api_secret = os.getenv("UPSTOX_API_SECRET")
        self.upstox_redirect_uri = os.getenv("UPSTOX_REDIRECT_URI")

    def get_token_bundle(
        self,
        broker_name: str,
        *,
        broker_user_id: Optional[str] = None,
        connection_id: Optional[int] = None,
    ) -> Optional[TokenBundle]:
        return self.token_store.get_tokens(
            broker_name,
            broker_user_id=broker_user_id,
            connection_id=connection_id,
        )

    def get_tokens(
        self,
        broker_name: str,
        *,
        broker_user_id: Optional[str] = None,
        connection_id: Optional[int] = None,
    ) -> Optional[dict]:
        bundle = self.get_token_bundle(
            broker_name, broker_user_id=broker_user_id, connection_id=connection_id
        )
        return bundle.to_config() if bundle else None

    def get_access_token(
        self,
        broker_name: str,
        *,
        broker_user_id: Optional[str] = None,
        connection_id: Optional[int] = None,
    ) -> Optional[str]:
        bundle = self.get_token_bundle(
            broker_name, broker_user_id=broker_user_id, connection_id=connection_id
        )
        return bundle.access_token if bundle else None

    def store_tokens(
        self,
        broker_name: str,
        tokens,
        broker_user_id: str | None = None,
        connection_id: int | None = None,
        user_id: int | None = None,
    ) -> None:
        self.token_store.store_tokens(
            broker_name,
            tokens,
            broker_user_id=broker_user_id,
            connection_id=connection_id,
            user_id=user_id,
        )

    def disconnect(
        self,
        broker_name: str,
        *,
        connection_id: int | None = None,
        user_id: int | None = None,
    ) -> bool:
        return self.token_store.disconnect(
            broker_name,
            connection_id=connection_id,
            user_id=user_id,
        )
