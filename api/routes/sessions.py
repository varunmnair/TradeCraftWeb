from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.dependencies import get_db_session, get_session_service, get_session_manager
from api.errors import ServiceError
from api.schemas.session import SessionResponse
from api.schemas.session import SessionStartRequest as SessionCreate
from db import models

router = APIRouter(prefix="/session", tags=["session"])


@router.post("", response_model=SessionResponse)
def create_session(
    payload: SessionCreate,
    db: Session = Depends(get_db_session),
    session_service=Depends(get_session_service),
    session_manager=Depends(get_session_manager),
):
    connection = (
        db.query(models.BrokerConnection)
        .filter(models.BrokerConnection.id == payload.broker_connection_id)
        .first()
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Broker connection not found")

    # Validate token is valid (not expired or missing)
    bundle = session_manager.get_token_bundle(connection.broker_name, connection_id=connection.id)
    
    if not bundle or not bundle.access_token:
        raise ServiceError(
            "No access token found. Please reconnect the broker.",
            error_code="invalid_token",
            http_status=401,
        )
    
    if bundle.expires_at:
        expires_dt = bundle.expires_at
        if isinstance(expires_dt, str):
            expires_dt = datetime.fromisoformat(expires_dt)
        if expires_dt.tzinfo is None:
            expires_dt = expires_dt.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) >= expires_dt:
            raise ServiceError(
                "Access token has expired. Please reconnect the broker.",
                error_code="invalid_token",
                http_status=401,
            )

    session_info = session_service.create_session(
        broker_connection=connection,
        warm_start=payload.warm_start,
    )
    return SessionResponse(**session_info)
