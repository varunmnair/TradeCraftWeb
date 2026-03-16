from __future__ import annotations

import hashlib
import logging
import os
import urllib.parse
from typing import Optional

import requests
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import HTMLResponse

from api import config
from api.dependencies import (
    get_auth_service,
    get_broker_auth_state_service,
    get_broker_connection_service,
    get_current_user,
    get_session_manager,
)
from api.errors import ServiceError
from api.schemas.common import ErrorResponse
from core.auth.context import UserContext
from core.session_manager import SessionManager
from core.services.auth_service import AuthService
from core.services.broker_auth_service import BrokerAuthStateService
from core.services.broker_connection_service import BrokerConnectionService

router = APIRouter(prefix="/brokers/upstox", tags=["brokers"])

UPSTOX_AUTH_URL = "https://api.upstox.com/v2/login/authorization/dialog"
UPSTOX_TOKEN_URL = "https://api.upstox.com/v2/login/authorization/token"


# --- API Models ---
class BrokerConnectResponse(BaseModel):
    authorize_url: str
    state: str
    connection_id: int


class ConnectionStatus(BaseModel):
    connection_id: int
    user_id: int
    connected: bool
    broker_user_id: Optional[str]
    token_updated_at: Optional[datetime]


class BrokerStatusResponse(BaseModel):
    connections: list[ConnectionStatus]


# --- Upstox Broker Connection ---


def _get_upstox_env() -> tuple[str, str, str]:
    from api import config
    client_id = config.UPSTOX_API_KEY
    client_secret = config.UPSTOX_API_SECRET
    redirect_uri = config.UPSTOX_REDIRECT_URI
    if not client_id or not client_secret or not redirect_uri:
        raise ServiceError(
            "Upstox API env vars missing",
            error_code="config_error",
            http_status=500,
        )
    return client_id, client_secret, redirect_uri


@router.get("/connect", response_model=BrokerConnectResponse)
def connect_upstox(
    connection_id: Optional[int] = Query(default=None),
    current_user: UserContext = Depends(get_current_user),
    broker_service: BrokerConnectionService = Depends(get_broker_connection_service),
    state_service: BrokerAuthStateService = Depends(get_broker_auth_state_service),
):
    if not current_user.user_id or not current_user.tenant_id:
        raise ServiceError("User context missing", error_code="unauthorized", http_status=401)
    connection = broker_service.ensure_connection(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        broker_name="upstox",
        connection_id=connection_id,
        allow_admin=current_user.is_admin(),
    )
    client_id, _, redirect_uri = _get_upstox_env()
    state = state_service.create_state(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        connection_id=connection.id,
        broker_name="upstox",
    )
    params = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )
    authorize_url = f"{UPSTOX_AUTH_URL}?{params}"
    return {"authorize_url": authorize_url, "state": state, "connection_id": connection.id}


def _render_html(message: str, success: bool) -> HTMLResponse:
    color = "#0f9d58" if success else "#d93025"
    body = f"""
    <html>
      <head><title>Upstox Connection</title></head>
      <body style='font-family: sans-serif; padding: 2rem;'>
        <h2 style='color:{color};'>{message}</h2>
        <p>You may close this tab.</p>
      </body>
    </html>
    """
    return HTMLResponse(content=body, status_code=200 if success else 400)


@router.get("/callback")
def upstox_callback(
    code: str,
    state: str,
    state_service: BrokerAuthStateService = Depends(get_broker_auth_state_service),
    broker_service: BrokerConnectionService = Depends(get_broker_connection_service),
    session_manager: SessionManager = Depends(get_session_manager),
    current_user: UserContext = Depends(get_current_user),
):
    if config.IS_DEV and not current_user.user_id:
        return _render_html("Authorization failed: DEV user missing", success=False)
    try:
        state_info = state_service.consume_state(state)
    except ValueError as exc:
        return _render_html(f"Authorization failed: {exc}", success=False)
    connection = broker_service.ensure_connection(
        tenant_id=state_info.tenant_id,
        user_id=state_info.user_id,
        broker_name="upstox",
        connection_id=state_info.connection_id,
        allow_admin=True,
    )
    client_id, client_secret, redirect_uri = _get_upstox_env()
    token_payload = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    try:
        response = requests.post(UPSTOX_TOKEN_URL, data=token_payload, timeout=30)
    except requests.RequestException as exc:
        return _render_html(f"Token exchange failed: {exc}", success=False)
    if response.status_code >= 400:
        return _render_html("Token exchange failed: upstream error", success=False)
    token_data = response.json()
    expires_value = token_data.get("expires_in")
    expires_iso = None
    if expires_value is not None:
        try:
            expires_seconds = int(expires_value)
            expires_iso = (datetime.now(timezone.utc) + timedelta(seconds=expires_seconds)).isoformat()
        except (ValueError, TypeError):
            expires_iso = None

    bundle_payload = {
        "access_token": token_data.get("access_token"),
        "extended_token": token_data.get("refresh_token"),
        "expires_at": expires_iso,
        "broker_user_id": token_data.get("user_id") or str(connection.user_id),
        "api_key": client_id,
        "api_secret": client_secret,
        "redirect_uri": redirect_uri,
        "obtained_at": datetime.now(timezone.utc).isoformat(),
        "raw_profile": token_data.get("profile"),
    }
    if not bundle_payload["access_token"]:
        return _render_html("Token exchange failed: missing access token", success=False)
    session_manager.store_tokens(
        "upstox",
        bundle_payload,
        connection_id=connection.id,
    )
    return _render_html(
        "✅ Upstox connected successfully. You may close this tab.", success=True
    )


@router.get("/status", response_model=BrokerStatusResponse)
def upstox_status(
    connection_id: Optional[int] = Query(default=None),
    current_user: UserContext = Depends(get_current_user),
    broker_service: BrokerConnectionService = Depends(get_broker_connection_service),
    session_manager: SessionManager = Depends(get_session_manager),
):
    if not current_user.user_id or not current_user.tenant_id:
        raise ServiceError("User context missing", error_code="unauthorized", http_status=401)
    connections = broker_service.list_connections(
        tenant_id=current_user.tenant_id,
        user_id=None if current_user.is_admin() else current_user.user_id,
    )
    upstox_connections = [conn for conn in connections if conn.broker_name == "upstox" and (connection_id is None or conn.id == connection_id)]
    if connection_id and not upstox_connections:
        raise ServiceError("Connection not found", error_code="not_found", http_status=404)
    statuses = []
    for conn in upstox_connections:
        bundle = session_manager.get_token_bundle("upstox", connection_id=conn.id)
        
        # Validate token by attempting a simple API call
        is_valid = False
        if bundle and bundle.access_token:
            try:
                import requests
                headers = {"Authorization": f"Bearer {bundle.access_token}"}
                response = requests.get(
                    "https://api.upstox.com/v2/user/profile",
                    headers=headers,
                    timeout=5
                )
                is_valid = response.status_code == 200
            except Exception:
                is_valid = False
        
        statuses.append(
            {
                "connection_id": conn.id,
                "user_id": conn.user_id,
                "connected": is_valid,
                "broker_user_id": bundle.broker_user_id if bundle else None,
                "token_updated_at": conn.token_updated_at.isoformat() if conn.token_updated_at else None,
            }
        )
    return {"connections": statuses}


# --- Zerodha API Models ---
class ZerodhaConnectResponse(BaseModel):
    authorize_url: str
    state: str
    connection_id: int


class ZerodhaConnectionStatus(BaseModel):
    connection_id: int
    user_id: int
    connected: bool
    broker_user_id: Optional[str] = None
    token_updated_at: Optional[datetime] = None


class ZerodhaStatusResponse(BaseModel):
    connections: list[ZerodhaConnectionStatus]


# --- Zerodha Broker Connection ---

zerodha_router = APIRouter(prefix="/brokers/zerodha", tags=["brokers"])

KITE_AUTH_URL = "https://kite.zerodha.com/connect/login"
KITE_TOKEN_URL = "https://api.kite.trade/session/token"


def _get_kite_env() -> tuple[str, str, str]:
    from api import config
    api_key = config.KITE_API_KEY
    api_secret = config.KITE_API_SECRET
    redirect_uri = config.KITE_REDIRECT_URI
    if not api_key or not api_secret or not redirect_uri:
        raise ServiceError(
            "Kite API env vars missing",
            error_code="config_error",
            http_status=500,
        )
    return api_key, api_secret, redirect_uri


@zerodha_router.get(
    "/connect",
    response_model=ZerodhaConnectResponse,
    responses={
        409: {"model": ErrorResponse, "description": "Upstox connection required for market data"},
    },
)
def connect_zerodha(
    connection_id: Optional[int] = Query(default=None),
    current_user: UserContext = Depends(get_current_user),
    broker_service: BrokerConnectionService = Depends(get_broker_connection_service),
    state_service: BrokerAuthStateService = Depends(get_broker_auth_state_service),
    session_manager: SessionManager = Depends(get_session_manager),
):
    if not current_user.user_id or not current_user.tenant_id:
        raise ServiceError("User context missing", error_code="unauthorized", http_status=401)

    # Prerequisite: check for an active Upstox connection
    upstox_connections = broker_service.list_connections(
        tenant_id=current_user.tenant_id, user_id=current_user.user_id
    )
    upstox_connected = [conn for conn in upstox_connections if conn.broker_name == "upstox"]
    upstox_is_connected = any(
        session_manager.get_token_bundle("upstox", connection_id=conn.id) for conn in upstox_connected
    )
    if not upstox_is_connected:
        raise ServiceError(
            "Upstox connection required for instruments/market data. Connect Upstox first.",
            error_code="upstox_required",
            http_status=409,
            context={"required_broker": "upstox"},
        )

    connection = broker_service.ensure_connection(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        broker_name="zerodha",
        connection_id=connection_id,
        allow_admin=current_user.is_admin(),
    )
    api_key, _, redirect_uri = _get_kite_env()
    state = state_service.create_state(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        connection_id=connection.id,
        broker_name="zerodha",
    )
    # Use redirect_params to include state in callback URL
    params = urllib.parse.urlencode({
        "v": 3,
        "api_key": api_key,
        "redirect_params": urllib.parse.urlencode({"state": state}),
    })
    authorize_url = f"{KITE_AUTH_URL}?{params}"
    return {"authorize_url": authorize_url, "state": state, "connection_id": connection.id}


@zerodha_router.get("/callback")
def zerodha_callback(
    request_token: str,
    state: str,
    state_service: BrokerAuthStateService = Depends(get_broker_auth_state_service),
    broker_service: BrokerConnectionService = Depends(get_broker_connection_service),
    session_manager: SessionManager = Depends(get_session_manager),
):
    try:
        state_info = state_service.consume_state(state)
    except ValueError as exc:
        return _render_html(f"Authorization failed: {exc}", success=False)

    connection = broker_service.ensure_connection(
        tenant_id=state_info.tenant_id,
        user_id=state_info.user_id,
        broker_name="zerodha",
        connection_id=state_info.connection_id,
        allow_admin=True,
    )
    api_key, api_secret, redirect_uri = _get_kite_env()
    checksum = hashlib.sha256(f"{api_key}{request_token}{api_secret}".encode("utf-8")).hexdigest()
    token_payload = {
        "api_key": api_key,
        "request_token": request_token,
        "checksum": checksum,
    }
    try:
        response = requests.post(KITE_TOKEN_URL, data=token_payload, timeout=30)
        response.raise_for_status()
        token_data = response.json()
    except requests.RequestException as exc:
        return _render_html(f"Token exchange failed: {exc}", success=False)
    except (ValueError, requests.HTTPError):
        return _render_html("Token exchange failed: upstream error", success=False)

    # Debug: log what we got
    import logging
    logging.debug(f"Kite token response: {token_data}")

    # Kite returns access_token inside "data" field
    access_token = token_data.get("data", {}).get("access_token") if isinstance(token_data, dict) else None
    if not access_token:
        return _render_html(f"Token exchange failed: missing access token. Response: {token_data}", success=False)

    bundle_payload = {
        "access_token": access_token,
        "public_token": token_data.get("data", {}).get("public_token"),
        "broker_user_id": token_data.get("data", {}).get("user_id"),
        "api_key": api_key,
        "api_secret": api_secret,
        "redirect_uri": redirect_uri,
        "obtained_at": datetime.now(timezone.utc).isoformat(),
        "raw_profile": token_data.get("data", {}),
    }

    session_manager.store_tokens(
        "zerodha",
        bundle_payload,
        connection_id=connection.id,
    )
    return _render_html("✅ Zerodha connected successfully. You may close this tab.", success=True)


@zerodha_router.get("/status", response_model=ZerodhaStatusResponse)
def zerodha_status(
    connection_id: Optional[int] = Query(default=None),
    current_user: UserContext = Depends(get_current_user),
    broker_service: BrokerConnectionService = Depends(get_broker_connection_service),
    session_manager: SessionManager = Depends(get_session_manager),
):
    if not current_user.user_id or not current_user.tenant_id:
        raise ServiceError("User context missing", error_code="unauthorized", http_status=401)

    connections = broker_service.list_connections(
        tenant_id=current_user.tenant_id,
        user_id=None if current_user.is_admin() else current_user.user_id,
    )
    zerodha_connections = [
        conn
        for conn in connections
        if conn.broker_name == "zerodha" and (connection_id is None or conn.id == connection_id)
    ]
    if connection_id and not zerodha_connections:
        raise ServiceError("Connection not found", error_code="not_found", http_status=404)

    statuses = []
    for conn in zerodha_connections:
        bundle = session_manager.get_token_bundle("zerodha", connection_id=conn.id)
        
        # Validate token by attempting to get profile
        is_valid = False
        if bundle and bundle.access_token:
            try:
                from brokers.zerodha_broker import ZerodhaBroker
                from api import config
                api_key = config.KITE_API_KEY or ""
                broker = ZerodhaBroker(
                    user_id=str(conn.user_id),
                    api_key=api_key,
                    access_token=bundle.access_token,
                )
                broker.login()  # This validates the token
                is_valid = True
            except Exception as e:
                logging.debug(f"Zerodha token validation failed: {e}")
                is_valid = False
        
        statuses.append(
            {
                "connection_id": conn.id,
                "user_id": conn.user_id,
                "connected": is_valid,
                "broker_user_id": bundle.broker_user_id if bundle else None,
                "token_updated_at": conn.token_updated_at.isoformat() if conn.token_updated_at else None,
            }
        )
    return {"connections": statuses}
