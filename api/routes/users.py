from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.dependencies import get_db_session
from api.schemas.user import UserCreate, UserResponse
from db import models

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db_session),
):
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = models.User(
        email=payload.email,
        display_name=payload.display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
