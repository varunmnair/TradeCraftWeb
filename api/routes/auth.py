from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.dependencies import DEV_MODE, get_auth_service, get_current_user
from api.errors import ServiceError
from api.schemas.auth import AuthResponse, LoginRequest, MeResponse, RegisterRequest
from core.auth.context import UserContext
from core.services.auth_service import AuthService


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=MeResponse)
def register(payload: RegisterRequest, auth_service: AuthService = Depends(get_auth_service)):
    if not DEV_MODE:
        raise ServiceError("Registration disabled", error_code="forbidden", http_status=403)
    user = auth_service.register_tenant(
        tenant_name=payload.tenant_name,
        email=payload.email,
        password=payload.password,
        role="admin",
    )
    if not user.user_id or not user.tenant_id:
        raise ServiceError("User creation failed", error_code="internal_error")
    return MeResponse(id=int(user.user_id), tenant_id=int(user.tenant_id), email=user.email, role=user.role)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, auth_service: AuthService = Depends(get_auth_service)):
    try:
        return auth_service.login(email=payload.email, password=payload.password)
    except ValueError as exc:
        raise ServiceError(str(exc), error_code="invalid_credentials", http_status=401) from exc


@router.post("/logout")
def logout(request: Request, current_user: UserContext = Depends(get_current_user)):
    return {"success": True}


@router.get("/me", response_model=MeResponse)
def me(current_user: UserContext = Depends(get_current_user)):
    if not current_user.user_id or not current_user.tenant_id:
        raise ServiceError("User context missing", error_code="unauthorized", http_status=401)
    return MeResponse(id=current_user.user_id, tenant_id=current_user.tenant_id, email=current_user.email, role=current_user.role)
