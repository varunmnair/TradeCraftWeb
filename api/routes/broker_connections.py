from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse

from api.dependencies import get_auth_service, get_current_user
from api.errors import ServiceError
from api.schemas.broker_connection import BrokerConnectionResponse
from core.services.auth_service import AuthService
from core.services.broker_connection_service import BrokerConnectionService

LOGGER = logging.getLogger("tradecraftx")

router = APIRouter(prefix="/broker-connections", tags=["broker_connections"])

_UI_DIST_PATH = Path(__file__).resolve().parents[2] / "ui" / "dist"


def get_service() -> BrokerConnectionService:
    from api.dependencies import get_broker_connection_service

    return get_broker_connection_service()


def _is_browser_navigation(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    fetch_mode = request.headers.get("sec-fetch-mode", "")
    return "text/html" in accept and fetch_mode in {"", "navigate"}


@router.get("", response_model=list[BrokerConnectionResponse])
def list_connections(
    request: Request,
    service: BrokerConnectionService = Depends(get_service),
    auth_service: AuthService = Depends(get_auth_service),
):
    # Mobile OAuth callback redirects here with ?oauth=...; browsers navigate as
    # GET /broker-connections, which collides with this API route. Serve the SPA
    # for browser navigations so the frontend can handle the OAuth result.
    if _is_browser_navigation(request):
        index_path = _UI_DIST_PATH / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))

    current_user = get_current_user(request, auth_service)
    if current_user.user_id is None:
        raise ServiceError(
            "User context incomplete", error_code="unauthorized", http_status=401
        )
    # Always show only current user's connections for security
    # Never allow user_id parameter to override - use current_user.user_id only
    LOGGER.info("list_connections: user_id=%s", current_user.user_id)
    connections = [
        conn
        for conn in service.list_connections(user_id=current_user.user_id)
        if conn.encrypted_tokens is not None or conn.broker_user_id is not None
    ]
    LOGGER.info(
        "list_connections: found %d connections for user_id=%s",
        len(connections),
        current_user.user_id,
    )
    return [BrokerConnectionResponse.from_orm(conn) for conn in connections]
