"""Admin endpoints for user management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.dependencies import get_auth_service, get_current_user
from api.errors import ServiceError
from core.auth.context import UserContext
from core.services.auth_service import AuthService


router = APIRouter(prefix="/admin", tags=["admin"])


class TradingEnabledRequest(BaseModel):
    enabled: bool


class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    trading_enabled: bool


def require_admin(current_user: UserContext = Depends(get_current_user)) -> UserContext:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.post("/users/{user_id}/trading-enabled", response_model=UserResponse)
def set_user_trading_enabled(
    user_id: int,
    payload: TradingEnabledRequest,
    current_user: UserContext = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Enable or disable trading for a user. Admin only."""
    try:
        user = auth_service.set_user_trading_enabled(user_id, payload.enabled, current_user.user_id)
        return UserResponse(
            id=user.id,
            email=user.email,
            role=user.role,
            trading_enabled=user.trading_enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    current_user: UserContext = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Get user details. Admin only."""
    user = auth_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        trading_enabled=user.trading_enabled,
    )
