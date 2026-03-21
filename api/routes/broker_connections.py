from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from api.dependencies import get_current_user
from api.errors import ServiceError
from api.schemas.broker_connection import BrokerConnectionResponse
from core.auth.context import UserContext
from core.services.broker_connection_service import BrokerConnectionService

LOGGER = logging.getLogger("tradecraftx")

router = APIRouter(prefix="/broker-connections", tags=["broker_connections"])


def get_service() -> BrokerConnectionService:
    from api.dependencies import get_broker_connection_service

    return get_broker_connection_service()


@router.get("", response_model=list[BrokerConnectionResponse])
def list_connections(
    service: BrokerConnectionService = Depends(get_service),
    current_user: UserContext = Depends(get_current_user),
):
    if current_user.user_id is None:
        raise ServiceError(
            "User context incomplete", error_code="unauthorized", http_status=401
        )
    # Always show only current user's connections for security
    # Never allow user_id parameter to override - use current_user.user_id only
    LOGGER.info("list_connections: user_id=%s", current_user.user_id)
    connections = service.list_connections(user_id=current_user.user_id)
    LOGGER.info(
        "list_connections: found %d connections for user_id=%s",
        len(connections),
        current_user.user_id,
    )
    return [BrokerConnectionResponse.from_orm(conn) for conn in connections]
