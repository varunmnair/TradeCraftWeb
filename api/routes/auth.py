from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from api import config
from api.dependencies import get_auth_service, get_current_user
from api.errors import ServiceError
from api.schemas.auth import (
    AuthResponse,
    LoginRequest,
    MeResponse,
    RegisterRequest,
)
from core.audit import log_audit
from core.auth.context import UserContext
from core.security.passwords import PasswordError
from core.security.rate_limiter import get_rate_limiter
from core.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_refresh_token_from_cookie(request: Request) -> str | None:
    return request.cookies.get(config.REFRESH_TOKEN_COOKIE_NAME)


def _create_refresh_cookie(refresh_token: str) -> dict:
    return {
        "key": config.REFRESH_TOKEN_COOKIE_NAME,
        "value": refresh_token,
        "httponly": True,
        "secure": config.COOKIE_SECURE,
        "samesite": config.COOKIE_SAMESITE,
        "max_age": config.REFRESH_TOKEN_COOKIE_MAX_AGE,
        "path": "/",
    }


def _clear_refresh_cookie() -> dict:
    return {
        "key": config.REFRESH_TOKEN_COOKIE_NAME,
        "value": "",
        "httponly": True,
        "secure": config.COOKIE_SECURE,
        "samesite": config.COOKIE_SAMESITE,
        "max_age": 0,
        "path": "/",
    }


@router.post("/register", response_model=MeResponse)
def register(
    payload: RegisterRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
):
    rate_limiter = get_rate_limiter()
    allowed, message = rate_limiter.check_rate_limit(request, "register")
    if not allowed:
        raise ServiceError(message, error_code="rate_limit_exceeded", http_status=429)

    try:
        user = auth_service.register_user(
            email=payload.email,
            password=payload.password,
            first_name=payload.first_name,
            last_name=payload.last_name,
            phone=payload.phone,
            role="user",
        )
    except PasswordError as exc:
        raise ServiceError(str(exc), error_code="invalid_password", http_status=400)
    except ValueError as exc:
        raise ServiceError(str(exc), error_code="invalid_request", http_status=400)

    rate_limiter.record_success(request, "register")

    return MeResponse(
        id=user.user_id,
        email=user.email,
        role=user.role,
    )


@router.post("/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
):
    rate_limiter = get_rate_limiter()
    allowed, message = rate_limiter.check_rate_limit(request, "login")
    if not allowed:
        raise ServiceError(message, error_code="rate_limit_exceeded", http_status=429)

    user_agent = request.headers.get("User-Agent")
    ip_address = request.headers.get(
        "X-Forwarded-For", request.client.host if request.client else None
    )

    try:
        result = auth_service.login(
            email=payload.email,
            password=payload.password,
            user_agent=user_agent,
            ip_address=ip_address,
        )
    except ValueError as exc:
        log_audit(
            action="login_failed",
            user=UserContext(
                user_id=0, email=payload.email, role="", trading_enabled=False
            ),
            resource_type="auth",
            metadata={"reason": "invalid_credentials"},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        raise ServiceError(str(exc), error_code="invalid_credentials", http_status=401)

    rate_limiter.record_success(request, "login")

    log_audit(
        action="login_success",
        user=UserContext(
            user_id=result.user_id,
            email=result.email,
            role=result.role,
            trading_enabled=result.trading_enabled,
        ),
        resource_type="auth",
        ip_address=ip_address,
        user_agent=user_agent,
    )

    response = JSONResponse(
        content=AuthResponse(
            access_token=result.access_token,
            token_type="bearer",
            user={
                "id": result.user_id,
                "email": result.email,
                "role": result.role,
                "trading_enabled": result.trading_enabled,
                "first_name": result.first_name,
                "last_name": result.last_name,
            },
        ).model_dump(),
    )
    response.set_cookie(**_create_refresh_cookie(result.refresh_token))
    return response


@router.post("/refresh", response_model=AuthResponse)
def refresh(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    rate_limiter = get_rate_limiter()
    allowed, message = rate_limiter.check_rate_limit(request, "refresh")
    if not allowed:
        raise ServiceError(message, error_code="rate_limit_exceeded", http_status=429)

    refresh_token = _get_refresh_token_from_cookie(request)
    if not refresh_token:
        raise ServiceError(
            "Refresh token not found", error_code="unauthorized", http_status=401
        )

    try:
        user_agent = request.headers.get("User-Agent")
        ip_address = request.headers.get(
            "X-Forwarded-For", request.client.host if request.client else None
        )

        result = auth_service.refresh(
            refresh_token=refresh_token,
            user_agent=user_agent,
            ip_address=ip_address,
        )
    except ValueError as exc:
        response.set_cookie(**_clear_refresh_cookie())
        raise ServiceError(str(exc), error_code="invalid_credentials", http_status=401)

    rate_limiter.record_success(request, "refresh")

    json_response = JSONResponse(
        content=AuthResponse(
            access_token=result.access_token,
            token_type="bearer",
            user={
                "id": result.user_id,
                "email": result.email,
                "role": result.role,
                "first_name": result.first_name,
                "last_name": result.last_name,
            },
        ).model_dump(),
    )
    json_response.set_cookie(**_create_refresh_cookie(result.refresh_token))
    return json_response


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
):
    import logging

    from api.dependencies import get_session_manager, get_session_registry

    logger = logging.getLogger("tradecraftx")

    refresh_token = _get_refresh_token_from_cookie(request)
    if refresh_token:
        auth_service = get_auth_service()
        auth_service.logout(refresh_token)

    if current_user.user_id:
        session_manager = get_session_manager()
        session_registry = get_session_registry()

        from api.dependencies import get_broker_connection_service

        broker_service = get_broker_connection_service()
        connections = broker_service.list_connections(
            user_id=current_user.user_id,
        )

        session_manager.disconnect("upstox", user_id=current_user.user_id)
        session_manager.disconnect("zerodha", user_id=current_user.user_id)

        for conn in connections:
            evicted = session_registry.evict_by_connection(conn.id)
            if evicted > 0:
                logger.info(
                    f"Evicted {evicted} sessions after logout disconnect for connection {conn.id}"
                )

    response = JSONResponse(content={"success": True})
    response.set_cookie(**_clear_refresh_cookie())
    return response


@router.get("/me", response_model=MeResponse)
def me(current_user: UserContext = Depends(get_current_user)):
    if not current_user.user_id:
        raise ServiceError(
            "User context missing", error_code="unauthorized", http_status=401
        )

    auth_service = get_auth_service()
    user = auth_service.get_user(current_user.user_id)
    if not user:
        raise ServiceError("User not found", error_code="not_found", http_status=404)

    broker_connections = auth_service.get_user_broker_connections(current_user.user_id)

    return MeResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        trading_enabled=user.trading_enabled,
        first_name=user.first_name,
        last_name=user.last_name,
        broker_connections=broker_connections,
    )
