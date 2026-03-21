from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.dependencies import get_db_session, get_session_service
from api.schemas.session import SessionResponse
from api.schemas.session import SessionStartRequest as SessionCreate
from db import models

router = APIRouter(prefix="/session", tags=["session"])


@router.post("", response_model=SessionResponse)
def create_session(
    payload: SessionCreate,
    db: Session = Depends(get_db_session),
    session_service=Depends(get_session_service),
):
    connection = (
        db.query(models.BrokerConnection)
        .filter(models.BrokerConnection.id == payload.broker_connection_id)
        .first()
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Broker connection not found")

    session_info = session_service.create_session(
        broker_connection=connection,
        warm_start=payload.warm_start,
    )
    return SessionResponse(**session_info)
