from __future__ import annotations

from fastapi import APIRouter, Depends

from api.dependencies import get_current_user
from api.errors import ServiceError
from api.schemas.broker_connection import BrokerConnectionCreate, BrokerConnectionResponse
from core.auth.context import UserContext
from core.services.broker_connection_service import BrokerConnectionService


router = APIRouter(prefix="/broker-connections", tags=["broker_connections"])


def get_service() -> BrokerConnectionService:
    from api.dependencies import get_broker_connection_service

    return get_broker_connection_service()


@router.post("", response_model=BrokerConnectionResponse)
def create_connection(
    payload: BrokerConnectionCreate,
    service: BrokerConnectionService = Depends(get_service),
    current_user: UserContext = Depends(get_current_user),
):
    if not payload.tokens:
        raise ServiceError("tokens payload required", error_code="invalid_request")
    if current_user.tenant_id is None or current_user.user_id is None:
        raise ServiceError("User context incomplete", error_code="unauthorized", http_status=401)
    target_user_id = payload.user_id or current_user.user_id
    if not current_user.is_admin() and target_user_id != current_user.user_id:
        raise ServiceError("Only admins can create connections for other users", error_code="forbidden", http_status=403)
    connection = service.create_connection(
        tenant_id=current_user.tenant_id,
        user_id=target_user_id,
        broker=payload.broker_name,
        tokens=payload.tokens,
        metadata=payload.metadata,
    )
    return BrokerConnectionResponse.from_orm(connection)


@router.get("", response_model=list[BrokerConnectionResponse])
def list_connections(
    user_id: int | None = None,
    service: BrokerConnectionService = Depends(get_service),
    current_user: UserContext = Depends(get_current_user),
):
    if current_user.tenant_id is None:
        raise ServiceError("User context incomplete", error_code="unauthorized", http_status=401)
    target_user_id = user_id if current_user.is_admin() else current_user.user_id
    connections = service.list_connections(tenant_id=current_user.tenant_id, user_id=target_user_id)
    return [BrokerConnectionResponse.from_orm(conn) for conn in connections]
