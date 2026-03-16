from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from api import config
from api.dependencies import get_broker_connection_service, get_current_user, get_session_registry, get_session_service
from api.errors import ServiceError
from api.schemas.common import ErrorResponse
from api.schemas.session import SessionResponse, SessionStartRequest
from core.auth.context import UserContext
from core.services.broker_connection_service import BrokerConnectionService
from core.services.session_service import SessionService
from core.runtime.session_registry import SessionRegistry
from kiteconnect.exceptions import TokenException


router = APIRouter(prefix="/session", tags=["session"])


@router.post(
    "/start",
    response_model=SessionResponse,
    responses={
        409: {"model": ErrorResponse, "description": "Upstox connection required for Zerodha trading"},
    },
)
def start_session(
    payload: SessionStartRequest,
    service: SessionService = Depends(get_session_service),
    connection_service: BrokerConnectionService = Depends(get_broker_connection_service),
    current_user: UserContext = Depends(get_current_user),
):
    if payload.broker_connection_id is not None:
        connection = connection_service.get_connection(payload.broker_connection_id)
        if not connection or connection.tenant_id != current_user.tenant_id:
            raise ServiceError("Broker connection not found", error_code="not_found", http_status=404)
        if not current_user.is_admin() and connection.user_id != current_user.user_id:
            raise ServiceError("Broker connection belongs to another user", error_code="forbidden", http_status=403)
        
        # Validate market data requirements for Zerodha
        market_data_connection_id = None
        if connection.broker_name == "zerodha":
            market_data_connection_id = payload.market_data_connection_id
            if market_data_connection_id is None:
                # Auto-find Upstox connection
                connections = connection_service.list_connections(
                    tenant_id=current_user.tenant_id,
                    user_id=current_user.user_id,
                )
                upstox_conn = None
                for conn in connections:
                    if conn.broker_name == "upstox":
                        # Check if it has valid tokens
                        from api.dependencies import get_session_manager
                        sm = get_session_manager()
                        if sm.get_token_bundle("upstox", connection_id=conn.id):
                            upstox_conn = conn
                            break
                if not upstox_conn:
                    raise ServiceError(
                        "Upstox connection required for market data when trading with Zerodha. Connect Upstox first.",
                        error_code="upstox_required",
                        http_status=409,
                        context={"required_broker": "upstox"},
                    )
                market_data_connection_id = upstox_conn.id
            else:
                # Validate provided market_data_connection_id
                md_connection = connection_service.get_connection(market_data_connection_id)
                if not md_connection or md_connection.broker_name != "upstox":
                    raise ServiceError(
                        "Market data provider must be Upstox",
                        error_code="invalid_market_data",
                        http_status=400,
                    )
        elif connection.broker_name == "upstox":
            # Upstox uses same connection for trading and market data
            market_data_connection_id = payload.broker_connection_id
        
        try:
            session = service.start_session(
                broker_connection_id=payload.broker_connection_id,
                market_data_connection_id=market_data_connection_id,
                warm_start=payload.warm_start,
            )
            return session
        except TokenException as e:
            raise ServiceError(
                f"Invalid or expired token: {str(e)}",
                error_code="invalid_token",
                http_status=401,
            )

    if not config.IS_DEV:
        raise ServiceError("broker_connection_id required", error_code="invalid_request", http_status=400)
    if not payload.broker_name or not payload.broker_config:
        raise ServiceError("broker_name and broker_config required in DEV_MODE", error_code="invalid_request", http_status=400)
    try:
        session = service.start_session(
            user_id=payload.session_user_id or current_user.email,
            broker_name=payload.broker_name,
            broker_config=payload.broker_config,
            warm_start=payload.warm_start,
        )
        return session
    except TokenException as e:
        raise ServiceError(
            f"Invalid or expired token: {str(e)}",
            error_code="invalid_token",
            http_status=401,
        )


class ActiveConnectionSetRequest(BaseModel):
    broker_connection_id: int


class ActiveConnectionResponse(BaseModel):
    broker_connection_id: int | None
    broker_name: str | None
    broker_user_id: str | None


@router.post("/active-connection", response_model=ActiveConnectionResponse)
def set_active_connection(
    payload: ActiveConnectionSetRequest,
    current_user: UserContext = Depends(get_current_user),
    connection_service: BrokerConnectionService = Depends(get_broker_connection_service),
):
    from core.auth.active_connection_store import get_active_connection_store

    if current_user.user_id is None:
        raise ServiceError("User context incomplete", error_code="unauthorized", http_status=401)

    connection = connection_service.get_connection(payload.broker_connection_id)
    if not connection:
        raise ServiceError("Connection not found", error_code="not_found", http_status=404)

    if connection.tenant_id != current_user.tenant_id:
        raise ServiceError("Connection belongs to another tenant", error_code="forbidden", http_status=403)

    if connection.user_id != current_user.user_id:
        raise ServiceError("Connection belongs to another user", error_code="forbidden", http_status=403)

    active_store = get_active_connection_store()
    active_store.set_active_connection(current_user.user_id, payload.broker_connection_id)

    return ActiveConnectionResponse(
        broker_connection_id=connection.id,
        broker_name=connection.broker_name,
        broker_user_id=connection.broker_user_id,
    )


@router.get("/active-connection", response_model=ActiveConnectionResponse)
def get_active_connection(
    current_user: UserContext = Depends(get_current_user),
    connection_service: BrokerConnectionService = Depends(get_broker_connection_service),
):
    from core.auth.active_connection_store import get_active_connection_store
    
    if current_user.user_id is None:
        raise ServiceError("User context incomplete", error_code="unauthorized", http_status=401)
    
    active_store = get_active_connection_store()
    connection_id = active_store.get_active_connection(current_user.user_id)
    
    if connection_id is None:
        return ActiveConnectionResponse(broker_connection_id=None, broker_name=None, broker_user_id=None)
    
    connection = connection_service.get_connection(connection_id)
    if not connection:
        active_store.clear_active_connection(current_user.user_id)
        return ActiveConnectionResponse(broker_connection_id=None, broker_name=None, broker_user_id=None)
    
    return ActiveConnectionResponse(
        broker_connection_id=connection.id,
        broker_name=connection.broker_name,
        broker_user_id=connection.broker_user_id,
    )


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: str,
    service: SessionService = Depends(get_session_service),
    registry: SessionRegistry = Depends(get_session_registry),
    current_user: UserContext = Depends(get_current_user),
):
    try:
        registry.require_access(session_id, current_user)
        return service.get_session_info(session_id)
    except ValueError as exc:
        raise ServiceError(str(exc), error_code="session_not_found", http_status=404) from exc


@router.post("/{session_id}/refresh", response_model=SessionResponse)
def refresh_session(
    session_id: str,
    service: SessionService = Depends(get_session_service),
    registry: SessionRegistry = Depends(get_session_registry),
    current_user: UserContext = Depends(get_current_user),
):
    try:
        registry.require_access(session_id, current_user)
        return service.refresh_caches(session_id)
    except ValueError as exc:
        raise ServiceError(str(exc), error_code="session_not_found", http_status=404) from exc


class ActiveConnectionSetRequest(BaseModel):
    broker_connection_id: int


class ActiveConnectionResponse(BaseModel):
    broker_connection_id: int | None
    broker_name: str | None
    broker_user_id: str | None


@router.post("/active-connection", response_model=ActiveConnectionResponse)
def set_active_connection(
    payload: ActiveConnectionSetRequest,
    current_user: UserContext = Depends(get_current_user),
    connection_service: BrokerConnectionService = Depends(get_broker_connection_service),
):
    from core.auth.active_connection_store import get_active_connection_store
    
    if current_user.user_id is None:
        raise ServiceError("User context incomplete", error_code="unauthorized", http_status=401)
    
    connection = connection_service.get_connection(payload.broker_connection_id)
    if not connection:
        raise ServiceError("Broker connection not found", error_code="not_found", http_status=404)
    
    if connection.tenant_id != current_user.tenant_id:
        raise ServiceError("Broker connection belongs to another tenant", error_code="forbidden", http_status=403)
    
    if connection.user_id != current_user.user_id:
        raise ServiceError("Broker connection belongs to another user", error_code="forbidden", http_status=403)
    
    active_store = get_active_connection_store()
    active_store.set_active_connection(current_user.user_id, payload.broker_connection_id)
    
    return ActiveConnectionResponse(
        broker_connection_id=connection.id,
        broker_name=connection.broker_name,
        broker_user_id=connection.broker_user_id,
    )


@router.get("/active-connection", response_model=ActiveConnectionResponse)
def get_active_connection(
    current_user: UserContext = Depends(get_current_user),
    connection_service: BrokerConnectionService = Depends(get_broker_connection_service),
):
    from core.auth.active_connection_store import get_active_connection_store
    
    if current_user.user_id is None:
        raise ServiceError("User context incomplete", error_code="unauthorized", http_status=401)
    
    active_store = get_active_connection_store()
    connection_id = active_store.get_active_connection(current_user.user_id)
    
    if connection_id is None:
        return ActiveConnectionResponse(broker_connection_id=None, broker_name=None, broker_user_id=None)
    
    connection = connection_service.get_connection(connection_id)
    if not connection:
        active_store.clear_active_connection(current_user.user_id)
        return ActiveConnectionResponse(broker_connection_id=None, broker_name=None, broker_user_id=None)
    
    return ActiveConnectionResponse(
        broker_connection_id=connection.id,
        broker_name=connection.broker_name,
        broker_user_id=connection.broker_user_id,
    )
