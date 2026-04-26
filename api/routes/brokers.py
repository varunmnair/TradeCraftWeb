from __future__ import annotations

import hashlib
import logging
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

import requests
from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from api import config
from api.dependencies import (
    get_broker_auth_state_service,
    get_broker_connection_service,
    get_current_user,
    get_session_manager,
)
from api.errors import ServiceError
from api.schemas.common import ErrorResponse
from core.auth.context import UserContext
from core.services.broker_auth_service import BrokerAuthStateService
from core.services.broker_connection_service import BrokerConnectionService
from core.session_manager import SessionManager

LOGGER = logging.getLogger("tradecraftx.brokers")

# --- Upstox Broker Connection ---

router = APIRouter(prefix="/brokers/upstox", tags=["brokers"])

UPSTOX_AUTH_URL = "https://api.upstox.com/v2/login/authorization/dialog"
UPSTOX_TOKEN_URL = "https://api.upstox.com/v2/login/authorization/token"


def _extract_jwt_expiration(token: str) -> Optional[datetime]:
    """Extract expiration timestamp from JWT token."""
    import base64
    import json
    try:
        token_parts = token.split(".")
        if len(token_parts) >= 2:
            padding = 4 - len(token_parts[1]) % 4
            if padding != 4:
                token_parts[1] += "=" * padding
            payload = base64.b64decode(token_parts[1])
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")
            token_payload = json.loads(payload)
            exp_timestamp = token_payload.get("exp")
            if exp_timestamp:
                return datetime.fromtimestamp(exp_timestamp, timezone.utc)
    except Exception:
        pass
    return None


class ConnectionStatus(BaseModel):
    connection_id: int
    broker_name: str
    connected: bool
    broker_user_id: Optional[str]
    token_updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    token_status: Literal["valid", "expired", "missing"] = "missing"


class BrokerConnectResponse(BaseModel):
    authorize_url: str
    state: str
    connection_id: int


class BrokerStatusResponse(BaseModel):
    connections: list[ConnectionStatus]


def _get_upstox_env() -> tuple[str, str, str]:
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
    if not current_user.user_id:
        raise ServiceError(
            "User context missing", error_code="unauthorized", http_status=401
        )
    connection = broker_service.ensure_connection(
        user_id=current_user.user_id,
        broker_name="upstox",
        connection_id=connection_id,
        allow_admin=current_user.is_admin(),
    )
    client_id, _, redirect_uri = _get_upstox_env()
    state = state_service.create_state(
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
    return {
        "authorize_url": authorize_url,
        "state": state,
        "connection_id": connection.id,
    }


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
):
    # State contains user_id, connection_id - no auth needed
    try:
        state_info = state_service.consume_state(state)
    except ValueError as exc:
        LOGGER.warning("Upstox callback: invalid state token: %s", exc)
        return _render_html(f"Authorization failed: {exc}", success=False)

    connection = broker_service.ensure_connection(
        user_id=state_info.user_id,
        broker_name="upstox",
        connection_id=state_info.connection_id,
        allow_admin=True,
    )

    # Idempotency check: if tokens already exist, return success
    existing_bundle = session_manager.get_token_bundle(
        "upstox", connection_id=connection.id
    )
    if existing_bundle and existing_bundle.access_token:
        LOGGER.info(
            "Upstox callback: tokens already exist for connection_id=%d, user_id=%d",
            connection.id,
            state_info.user_id,
        )
        return _render_html(
            "Upstox already connected. You may close this tab.", success=True
        )

    client_id, client_secret, redirect_uri = _get_upstox_env()
    token_payload = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    LOGGER.info(
        "Upstox callback: client_id=%s, redirect_uri=%s", client_id, redirect_uri
    )
    try:
        response = requests.post(UPSTOX_TOKEN_URL, data=token_payload, timeout=30)
    except requests.RequestException as exc:
        LOGGER.error("Upstox callback: token exchange request failed: %s", exc)
        return _render_html(f"Token exchange failed: {exc}", success=False)

    response_text = response.text
    print(
        f"Upstox callback DEBUG: status={response.status_code}, body={response_text[:500]}"
    )
    LOGGER.info(
        "Upstox callback: token_response status=%d, body=%s",
        response.status_code,
        response_text[:1500],
    )

    if response.status_code >= 400:
        # Try to parse the error response for better debugging
        try:
            error_json = response.json()
            # Upstox error format: {"status":"error","errors":[{"errorCode":"...","message":"..."}]}
            errors_list = error_json.get("errors", [])
            if errors_list and len(errors_list) > 0:
                error_code = errors_list[0].get("errorCode", "")
                error_message = errors_list[0].get("message", "upstream error")
            else:
                error_code = error_json.get("code", "")
                error_message = error_json.get("message", "upstream error")
            print(
                f"Upstox callback DEBUG: error_code={error_code}, error_message={error_message}"
            )
            LOGGER.error(
                "Upstox token exchange failed: code=%s, message=%s",
                error_code,
                error_message,
            )
        except Exception:
            error_message = f"upstream error (status {response.status_code})"
            print("Upstox callback DEBUG: failed to parse error JSON")
        return _render_html(f"Token exchange failed: {error_message}", success=False)
    token_data = response.json()
    expires_value = token_data.get("expires_in")
    expires_iso = None
    if expires_value is not None:
        try:
            expires_seconds = int(expires_value)
            expires_iso = (
                datetime.now(timezone.utc) + timedelta(seconds=expires_seconds)
            ).isoformat()
        except (ValueError, TypeError):
            expires_iso = None
    
    # If expires_in not provided, extract expiration from JWT token
    if not expires_iso and token_data.get("access_token"):
        import base64
        try:
            token_parts = token_data["access_token"].split(".")
            if len(token_parts) >= 2:
                # Add padding if needed
                padding = 4 - len(token_parts[1]) % 4
                if padding != 4:
                    token_parts[1] += "=" * padding
                payload = base64.b64decode(token_parts[1])
                if isinstance(payload, bytes):
                    payload = payload.decode("utf-8")
                import json
                token_payload = json.loads(payload)
                exp_timestamp = token_payload.get("exp")
                if exp_timestamp:
                    expires_iso = datetime.fromtimestamp(exp_timestamp, timezone.utc).isoformat()
        except Exception as e:
            LOGGER.warning("Failed to extract JWT expiration: %s", e)

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
        return _render_html(
            "Token exchange failed: missing access token", success=False
        )
    session_manager.store_tokens(
        "upstox",
        bundle_payload,
        connection_id=connection.id,
    )
    
    broker_user_id_from_oauth = token_data.get("user_id")
    if broker_user_id_from_oauth:
        from db.database import SessionLocal
        from db import models
        db = SessionLocal()
        try:
            conn_record = db.get(models.BrokerConnection, connection.id)
            if conn_record:
                conn_record.broker_user_id = broker_user_id_from_oauth
                db.commit()
        finally:
            db.close()
    
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
    if not current_user.user_id:
        raise ServiceError(
            "User context missing", error_code="unauthorized", http_status=401
        )
    # Always show only the current user's connections - never return other users' connections
    LOGGER.info("upstox_status: current_user.user_id=%s", current_user.user_id)
    connections = broker_service.list_connections(
        user_id=current_user.user_id,
    )
    upstox_connections = [
        conn
        for conn in connections
        if conn.broker_name == "upstox"
        and (connection_id is None or conn.id == connection_id)
    ]
    if connection_id and not upstox_connections:
        raise ServiceError(
            "Connection not found", error_code="not_found", http_status=404
        )

    # Return ALL connections with their actual status (connected/expired/missing)
    statuses = []
    for conn in upstox_connections:
        bundle = session_manager.get_token_bundle("upstox", connection_id=conn.id)

        # Determine token status
        token_status: Literal["valid", "expired", "missing"] = "missing"
        is_connected = False
        expires_at_val = None

        if bundle is not None and bundle.access_token is not None:
            # Check token expiration
            expires_dt = None
            
            # First check bundle.expires_at
            if bundle.expires_at:
                expires_dt = bundle.expires_at
                if isinstance(expires_dt, str):
                    expires_dt = datetime.fromisoformat(expires_dt)
                if expires_dt.tzinfo is None:
                    expires_dt = expires_dt.replace(tzinfo=timezone.utc)
            
            # If no expires_at, extract from JWT token
            if not expires_dt:
                expires_dt = _extract_jwt_expiration(bundle.access_token)
            
            if expires_dt:
                expires_at_val = conn.token_updated_at.isoformat() if conn.token_updated_at else None
                if datetime.now(timezone.utc) >= expires_dt:
                    token_status = "expired"
                else:
                    token_status = "valid"
                    is_connected = True
            else:
                # No expiry found - assume valid (for extended tokens etc)
                token_status = "valid"
                is_connected = True

        statuses.append(
            {
                "connection_id": conn.id,
                "broker_name": "upstox",
                "connected": is_connected,
                "broker_user_id": bundle.broker_user_id if bundle else None,
                "token_updated_at": (
                    conn.token_updated_at.isoformat()
                    if conn.token_updated_at
                    else None
                ),
                "expires_at": expires_at_val,
                "token_status": token_status,
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
        409: {
            "model": ErrorResponse,
            "description": "Upstox connection required for market data",
        },
    },
)
def connect_zerodha(
    connection_id: Optional[int] = Query(default=None),
    current_user: UserContext = Depends(get_current_user),
    broker_service: BrokerConnectionService = Depends(get_broker_connection_service),
    state_service: BrokerAuthStateService = Depends(get_broker_auth_state_service),
    session_manager: SessionManager = Depends(get_session_manager),
):
    if not current_user.user_id:
        raise ServiceError(
            "User context missing", error_code="unauthorized", http_status=401
        )

    # No Upstox prerequisite - Zerodha can be connected independently
    # Market data (Upstox) is optional and separate from trading data (Zerodha)

    connection = broker_service.ensure_connection(
        user_id=current_user.user_id,
        broker_name="zerodha",
        connection_id=connection_id,
        allow_admin=current_user.is_admin(),
    )
    api_key, _, redirect_uri = _get_kite_env()
    state = state_service.create_state(
        user_id=current_user.user_id,
        connection_id=connection.id,
        broker_name="zerodha",
    )
    # Use redirect_params to include state in callback URL
    params = urllib.parse.urlencode(
        {
            "v": 3,
            "api_key": api_key,
            "redirect_params": urllib.parse.urlencode({"state": state}),
        }
    )
    authorize_url = f"{KITE_AUTH_URL}?{params}"
    return {
        "authorize_url": authorize_url,
        "state": state,
        "connection_id": connection.id,
    }


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
        LOGGER.warning("Zerodha callback: invalid state token: %s", exc)
        return _render_html(f"Authorization failed: {exc}", success=False)

    connection = broker_service.ensure_connection(
        user_id=state_info.user_id,
        broker_name="zerodha",
        connection_id=state_info.connection_id,
        allow_admin=True,
    )

    # Idempotency check: if tokens already exist, return success
    existing_bundle = session_manager.get_token_bundle(
        "zerodha", connection_id=connection.id
    )
    if existing_bundle and existing_bundle.access_token:
        LOGGER.info(
            "Zerodha callback: tokens already exist for connection_id=%d, user_id=%d",
            connection.id,
            state_info.user_id,
        )
        return _render_html(
            "Zerodha already connected. You may close this tab.", success=True
        )

    api_key, api_secret, redirect_uri = _get_kite_env()
    checksum = hashlib.sha256(
        f"{api_key}{request_token}{api_secret}".encode("utf-8")
    ).hexdigest()
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
    access_token = (
        token_data.get("data", {}).get("access_token")
        if isinstance(token_data, dict)
        else None
    )
    if not access_token:
        return _render_html(
            f"Token exchange failed: missing access token. Response: {token_data}",
            success=False,
        )

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
    
    # Extract expiration from Zerodha token (check both JWT exp and kite expiry_timestamp)
    expires_iso = None
    kite_data = token_data.get("data", {})
    
    # Method 1: Check for kite expiry_timestamp (Zerodha specific)
    expiry_ts = kite_data.get("expiry_timestamp")
    if expiry_ts:
        try:
            expires_iso = datetime.fromtimestamp(int(expiry_ts), timezone.utc).isoformat()
        except (ValueError, TypeError):
            pass
    
    # Method 2: Extract from JWT if available
    if not expires_iso and access_token:
        import base64
        try:
            token_parts = access_token.split(".")
            if len(token_parts) >= 2:
                padding = 4 - len(token_parts[1]) % 4
                if padding != 4:
                    token_parts[1] += "=" * padding
                payload = base64.b64decode(token_parts[1])
                if isinstance(payload, bytes):
                    payload = payload.decode("utf-8")
                import json
                token_payload = json.loads(payload)
                exp_timestamp = token_payload.get("exp")
                if exp_timestamp:
                    expires_iso = datetime.fromtimestamp(exp_timestamp, timezone.utc).isoformat()
        except Exception as e:
            LOGGER.warning("Failed to extract JWT expiration for Zerodha: %s", e)
    
    if expires_iso:
        bundle_payload["expires_at"] = expires_iso

    LOGGER.info(
        "Zerodha token exchange successful, storing tokens for connection_id=%d",
        connection.id,
    )

    try:
        session_manager.store_tokens(
            "zerodha",
            bundle_payload,
            connection_id=connection.id,
        )
        LOGGER.info(
            "Zerodha tokens stored successfully for connection_id=%d", connection.id
        )
    except Exception as e:
        LOGGER.error(
            "Failed to store zerodha tokens for connection_id=%d: %s", connection.id, e
        )
        return _render_html(f"Failed to store tokens: {e}", success=False)

    broker_user_id_from_oauth = token_data.get("data", {}).get("user_id")
    if broker_user_id_from_oauth:
        from db.database import SessionLocal
        from db import models
        db = SessionLocal()
        try:
            conn_record = db.get(models.BrokerConnection, connection.id)
            if conn_record:
                conn_record.broker_user_id = broker_user_id_from_oauth
                db.commit()
        finally:
            db.close()

    return _render_html(
        "✅ Zerodha connected successfully. You may close this tab.", success=True
    )


@zerodha_router.get("/status", response_model=ZerodhaStatusResponse)
def zerodha_status(
    connection_id: Optional[int] = Query(default=None),
    current_user: UserContext = Depends(get_current_user),
    broker_service: BrokerConnectionService = Depends(get_broker_connection_service),
    session_manager: SessionManager = Depends(get_session_manager),
):
    if not current_user.user_id:
        raise ServiceError(
            "User context missing", error_code="unauthorized", http_status=401
        )

    # Always show only the current user's connections - never return other users' connections
    connections = broker_service.list_connections(
        user_id=current_user.user_id,
    )
    zerodha_connections = [
        conn
        for conn in connections
        if conn.broker_name == "zerodha"
        and (connection_id is None or conn.id == connection_id)
    ]
    if connection_id and not zerodha_connections:
        raise ServiceError(
            "Connection not found", error_code="not_found", http_status=404
        )

    # Return ALL connections with their actual status (connected/expired/missing)
    statuses = []
    for conn in zerodha_connections:
        try:
            bundle = session_manager.get_token_bundle("zerodha", connection_id=conn.id)
            
            # Determine token status
            token_status: Literal["valid", "expired", "missing"] = "missing"
            is_connected = False
            expires_at_val = None
            broker_user_id = None

            if bundle is not None and bundle.access_token is not None:
                broker_user_id = bundle.broker_user_id
                # Check token expiration
                expires_dt = None
                
                # First check bundle.expires_at
                if bundle.expires_at:
                    expires_dt = bundle.expires_at
                    if isinstance(expires_dt, str):
                        expires_dt = datetime.fromisoformat(expires_dt)
                    if expires_dt.tzinfo is None:
                        expires_dt = expires_dt.replace(tzinfo=timezone.utc)
                
                # If no expires_at, extract from JWT token
                if not expires_dt:
                    expires_dt = _extract_jwt_expiration(bundle.access_token)
                
                if expires_dt:
                    expires_at_val = conn.token_updated_at.isoformat() if conn.token_updated_at else None
                    if datetime.now(timezone.utc) >= expires_dt:
                        token_status = "expired"
                    else:
                        token_status = "valid"
                        is_connected = True
                else:
                    # No expiry found - assume valid
                    token_status = "valid"
                    is_connected = True
        except Exception as e:
            LOGGER.error(f"Error getting zerodha bundle for connection {conn.id}: {e}")
            token_status = "missing"
            is_connected = False
            broker_user_id = None
            expires_at_val = None

        statuses.append(
            {
                "connection_id": conn.id,
                "user_id": conn.user_id,
                "connected": is_connected,
                "broker_user_id": broker_user_id,
                "token_updated_at": (
                    conn.token_updated_at.isoformat()
                    if conn.token_updated_at
                    else None
                ),
                "expires_at": expires_at_val,
                "token_status": token_status,
            }
        )
    return {"connections": statuses}


@zerodha_router.post("/disconnect")
def zerodha_disconnect(
    current_user: UserContext = Depends(get_current_user),
    broker_service: BrokerConnectionService = Depends(get_broker_connection_service),
    session_manager: SessionManager = Depends(get_session_manager),
):
    if not current_user.user_id:
        raise ServiceError(
            "User context missing", error_code="unauthorized", http_status=401
        )

    # Get connection ID before disconnecting
    connections = broker_service.list_connections(
        user_id=current_user.user_id,
    )
    zerodha_conns = [c for c in connections if c.broker_name == "zerodha"]
    connection_id = zerodha_conns[0].id if zerodha_conns else None

    # Disconnect broker tokens
    session_manager.disconnect(
        "zerodha",
        user_id=current_user.user_id,
    )

    # Evict any sessions using this connection
    if connection_id:
        from api.dependencies import get_session_registry

        registry = get_session_registry()
        evicted = registry.evict_by_connection(connection_id)
        LOGGER.info(f"Evicted {evicted} sessions after Zerodha disconnect")

    return {"disconnected": True, "broker": "zerodha"}


class TradebookUploadResponse(BaseModel):
    rows_ingested: int
    symbols_covered: int
    errors: list[str]


@zerodha_router.post("/tradebook/upload", response_model=TradebookUploadResponse)
async def zerodha_tradebook_upload(
    file: UploadFile = File(...),
    current_user: UserContext = Depends(get_current_user),
):
    """Upload Zerodha tradebook CSV."""
    from api.dependencies import get_trades_service

    if not current_user.user_id:
        raise ServiceError(
            "User context missing", error_code="unauthorized", http_status=401
        )

    content = await file.read()
    text_content = content.decode("utf-8")

    trades_service = get_trades_service()
    result = trades_service.upload_zerodha_tradebook(current_user.user_id, text_content)

    return TradebookUploadResponse(**result)


@router.post("/disconnect")
def upstox_disconnect(
    current_user: UserContext = Depends(get_current_user),
    broker_service: BrokerConnectionService = Depends(get_broker_connection_service),
    session_manager: SessionManager = Depends(get_session_manager),
):
    if not current_user.user_id:
        raise ServiceError(
            "User context missing", error_code="unauthorized", http_status=401
        )

    # Get connection ID before disconnecting
    connections = broker_service.list_connections(
        user_id=current_user.user_id,
    )
    upstox_conns = [c for c in connections if c.broker_name == "upstox"]
    connection_id = upstox_conns[0].id if upstox_conns else None

    # Disconnect broker tokens
    session_manager.disconnect(
        "upstox",
        user_id=current_user.user_id,
    )

    # Evict any sessions using this connection
    if connection_id:
        from api.dependencies import get_session_registry

        registry = get_session_registry()
        evicted = registry.evict_by_connection(connection_id)
        LOGGER.info(f"Evicted {evicted} sessions after Upstox disconnect")

    return {"disconnected": True, "broker": "upstox"}


@router.post("/trades/sync")
def upstox_trades_sync(
    days: int = Query(default=400, ge=1, le=400),
    current_user: UserContext = Depends(get_current_user),
    session_manager: SessionManager = Depends(get_session_manager),
    broker_service: BrokerConnectionService = Depends(get_broker_connection_service),
):
    """Sync Upstox orders/trades to user_trades table."""
    if not current_user.user_id:
        raise ServiceError(
            "User context missing", error_code="unauthorized", http_status=401
        )

    from api.dependencies import JOB_TRADES_SYNC, get_job_runner

    connections = broker_service.list_connections(
        user_id=current_user.user_id,
    )
    upstox_conns = [
        c
        for c in connections
        if c.broker_name == "upstox" and c.user_id == current_user.user_id
    ]
    if not upstox_conns:
        raise ServiceError(
            "No Upstox connection found", error_code="no_connection", http_status=404
        )

    connection = upstox_conns[0]
    token_bundle = session_manager.get_token_bundle(
        "upstox", connection_id=connection.id
    )
    if not token_bundle:
        raise ServiceError(
            "Upstox not connected", error_code="not_connected", http_status=409
        )

    job_runner = get_job_runner()
    job_id = job_runner.start_job(
        session_id=f"trades-sync-{current_user.user_id}",
        job_type=JOB_TRADES_SYNC,
        payload={
            "user_id": current_user.user_id,
            "connection_id": connection.id,
            "days": days,
        },
    )

    return {"job_id": job_id}
