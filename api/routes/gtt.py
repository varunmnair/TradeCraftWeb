from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Header

from api.dependencies import (
    JOB_GTT_APPLY,
    JOB_GTT_PREVIEW,
    get_confirm_token_service,
    get_current_user,
    get_gtt_service,
    get_job_runner,
    get_placement_guard,
    get_session_registry,
    require_premium,
    require_trading_enabled,
)
from api.errors import ServiceError
from api.schemas.common import JobQueuedResponse
from api.schemas.gtt import (
    GTTAdjustRequest,
    GTTAdjustResponse,
    GTTApplyRequest,
    GTTConfirmRequest,
    GTTConfirmResponse,
    GTTDeleteRequest,
    GTTDeleteResponse,
    GTTOrdersResponse,
    GTTPreviewRequest,
)
from core.audit import log_audit
from core.auth.context import UserContext
from core.runtime.job_runner import JobRunner
from core.runtime.session_registry import SessionRegistry
from core.security.confirm_token_store import ConfirmTokenStore
from core.services.gtt_service import GTTService
from core.services.placement_guard import (
    PlacementConflictError,
    PlacementContextError,
    PlacementGuardService,
    placement_error_code,
    resolve_idempotency_key,
    validate_placement_context,
)

router = APIRouter(prefix="/gtt", tags=["gtt"])


def _placement_context(registry, session_id: str, current_user):
    try:
        return validate_placement_context(
            registry=registry,
            session_id=session_id,
            user=current_user,
        )
    except PlacementContextError as exc:
        raise ServiceError(
            str(exc),
            error_code=placement_error_code(exc),
            http_status=exc.http_status,
            context={"reason": exc.reason},
        ) from exc


@router.get("/{session_id}", response_model=GTTOrdersResponse)
def list_gtt_orders(
    session_id: str,
    service: GTTService = Depends(get_gtt_service),
    registry: SessionRegistry = Depends(get_session_registry),
    current_user: UserContext = Depends(get_current_user),
):
    try:
        registry.require_access(session_id, current_user)
        return service.analyze_orders(session_id)
    except ValueError as exc:
        raise ServiceError(
            str(exc), error_code="session_not_found", http_status=404
        ) from exc


@router.post("/preview", response_model=JobQueuedResponse)
def preview_gtt(
    payload: GTTPreviewRequest,
    job_runner: JobRunner = Depends(get_job_runner),
    registry: SessionRegistry = Depends(get_session_registry),
    current_user: UserContext = Depends(get_current_user),
):
    require_trading_enabled(current_user)
    _placement_context(registry, payload.session_id, current_user)

    log_audit(
        action="gtt_preview",
        user=current_user,
        resource_type="gtt",
        resource_id=payload.session_id,
    )

    job_id = job_runner.start_job(
        session_id=payload.session_id,
        job_type=JOB_GTT_PREVIEW,
        payload={"plan": payload.plan},
    )
    return JobQueuedResponse(job_id=job_id)


@router.post("/confirm", response_model=GTTConfirmResponse)
def confirm_gtt(
    payload: GTTConfirmRequest,
    confirm_store: ConfirmTokenStore = Depends(get_confirm_token_service),
    registry: SessionRegistry = Depends(get_session_registry),
    current_user: UserContext = Depends(get_current_user),
    idempotency_header: str | None = Header(default=None, alias="Idempotency-Key"),
):
    require_trading_enabled(current_user)
    require_premium(current_user)
    context = _placement_context(registry, payload.session_id, current_user)
    explicit_key = payload.idempotency_key or idempotency_header
    idempotency_key, _ = resolve_idempotency_key(
        user_id=current_user.user_id or 0,
        session_id=payload.session_id,
        device_id=current_user.device_id,
        payload={"scope": "gtt", "plan": payload.plan},
        explicit_key=explicit_key,
    )

    log_audit(
        action="gtt_confirm",
        user=current_user,
        resource_type="gtt",
        resource_id=payload.session_id,
        metadata={
            "idempotency_key": idempotency_key,
            "broker_connection_id": context["broker_connection_id"],
        },
    )

    issued = confirm_store.issue(
        session_id=payload.session_id,
        user_id=current_user.user_id,
        payload={
            "plan": payload.plan,
            "idempotency_key": idempotency_key,
        },
    )
    return GTTConfirmResponse(**issued)


@router.post("/apply", response_model=JobQueuedResponse)
def apply_gtt(
    payload: GTTApplyRequest,
    job_runner: JobRunner = Depends(get_job_runner),
    confirm_store: ConfirmTokenStore = Depends(get_confirm_token_service),
    registry: SessionRegistry = Depends(get_session_registry),
    placement_guard: PlacementGuardService = Depends(get_placement_guard),
    current_user: UserContext = Depends(get_current_user),
    idempotency_header: str | None = Header(default=None, alias="Idempotency-Key"),
):
    require_trading_enabled(current_user)
    require_premium(current_user)
    if not current_user.user_id:
        raise ServiceError("User context missing", error_code="unauthorized", http_status=401)
    context = _placement_context(registry, payload.session_id, current_user)

    explicit_key = payload.idempotency_key or idempotency_header
    idempotency_key, fingerprint = resolve_idempotency_key(
        user_id=current_user.user_id,
        session_id=payload.session_id,
        device_id=current_user.device_id,
        payload={
            "scope": "gtt",
            "plan": payload.plan,
        },
        explicit_key=explicit_key,
    )

    try:
        claim = placement_guard.claim(
            user_id=current_user.user_id,
            idempotency_key=idempotency_key,
            request_hash_value=fingerprint,
            context=context,
        )
    except PlacementConflictError as exc:
        raise ServiceError(
            str(exc), error_code="duplicate_placement", http_status=exc.http_status
        ) from exc

    if not claim["claimed"]:
        stored = json.loads(claim["record"].get("result_json") or "{}")
        job_id = stored.get("job_id")
        if job_id:
            return JobQueuedResponse(
                job_id=job_id,
                idempotency_key=idempotency_key,
                replayed=True,
            )

    try:
        confirm_store.verify(
            token=payload.confirmation_token,
            session_id=payload.session_id,
            user_id=current_user.user_id,
            payload={
                "plan": payload.plan,
                "idempotency_key": idempotency_key,
            },
        )
    except ValueError as exc:
        placement_guard.complete(
            user_id=current_user.user_id,
            idempotency_key=idempotency_key,
            status="failed",
            error=str(exc),
        )
        raise ServiceError(
            str(exc), error_code="invalid_token", http_status=400
        ) from exc

    log_audit(
        action="gtt_apply",
        user=current_user,
        resource_type="gtt",
        resource_id=payload.session_id,
        metadata={
            "symbols": [p.get("symbol") for p in payload.plan if p.get("symbol")],
            "idempotency_key": idempotency_key,
            "broker_connection_id": context["broker_connection_id"],
        },
    )

    job_id = job_runner.start_job(
        session_id=payload.session_id,
        job_type=JOB_GTT_APPLY,
        payload={
            "plan": payload.plan,
            "idempotency_key": idempotency_key,
            "user_id": current_user.user_id,
        },
    )
    placement_guard.complete(
        user_id=current_user.user_id,
        idempotency_key=idempotency_key,
        status="queued",
        result={"job_id": job_id},
    )
    return JobQueuedResponse(job_id=job_id, idempotency_key=idempotency_key)


@router.post("/delete", response_model=GTTDeleteResponse)
def delete_gtt_orders(
    payload: GTTDeleteRequest,
    service: GTTService = Depends(get_gtt_service),
    registry: SessionRegistry = Depends(get_session_registry),
    current_user: UserContext = Depends(get_current_user),
):
    require_trading_enabled(current_user)
    registry.require_access(payload.session_id, current_user)

    log_audit(
        action="gtt_delete",
        user=current_user,
        resource_type="gtt",
        resource_id=payload.session_id,
        metadata={"order_ids": payload.order_ids},
    )

    try:
        result = service.delete_orders_by_ids(payload.session_id, payload.order_ids)
        return GTTDeleteResponse(
            deleted=result.get("deleted", []), count=len(result.get("deleted", []))
        )
    except Exception as exc:
        raise ServiceError(
            str(exc), error_code="delete_failed", http_status=500
        ) from exc


@router.post("/adjust", response_model=GTTAdjustResponse)
def adjust_gtt_orders(
    payload: GTTAdjustRequest,
    service: GTTService = Depends(get_gtt_service),
    registry: SessionRegistry = Depends(get_session_registry),
    placement_guard: PlacementGuardService = Depends(get_placement_guard),
    current_user: UserContext = Depends(get_current_user),
    idempotency_header: str | None = Header(default=None, alias="Idempotency-Key"),
):
    require_trading_enabled(current_user)
    if not current_user.user_id:
        raise ServiceError("User context missing", error_code="unauthorized", http_status=401)
    context = _placement_context(registry, payload.session_id, current_user)

    idempotency_key, fingerprint = resolve_idempotency_key(
        user_id=current_user.user_id,
        session_id=payload.session_id,
        device_id=current_user.device_id,
        payload={
            "scope": "gtt_adjust",
            "order_ids": sorted(payload.order_ids),
            "target_variance": payload.target_variance,
            "broker_connection_id": context["broker_connection_id"],
        },
        explicit_key=payload.idempotency_key or idempotency_header,
    )
    try:
        claim = placement_guard.claim(
            user_id=current_user.user_id,
            idempotency_key=idempotency_key,
            request_hash_value=fingerprint,
            context=context,
        )
    except PlacementConflictError as exc:
        raise ServiceError(
            str(exc), error_code="duplicate_placement", http_status=exc.http_status
        ) from exc

    if not claim["claimed"]:
        stored = json.loads(claim["record"].get("result_json") or "{}")
        return GTTAdjustResponse(
            adjusted=stored.get("adjusted", []),
            failed=stored.get("failed", []),
            count=stored.get("count", 0),
            replayed=True,
        )

    log_audit(
        action="gtt_adjust",
        user=current_user,
        resource_type="gtt",
        resource_id=payload.session_id,
        metadata={
            "order_ids": payload.order_ids,
            "target_variance": payload.target_variance,
            "idempotency_key": idempotency_key,
            "broker_connection_id": context["broker_connection_id"],
        },
    )

    try:
        result = service.adjust_orders_by_ids(
            payload.session_id, payload.order_ids, payload.target_variance
        )
    except Exception as exc:
        placement_guard.complete(
            user_id=current_user.user_id,
            idempotency_key=idempotency_key,
            status="failed",
            error=str(exc),
        )
        raise ServiceError(
            str(exc), error_code="adjust_failed", http_status=500
        ) from exc

    response = GTTAdjustResponse(
        adjusted=result.get("adjusted", []),
        failed=result.get("failed", []),
        count=result.get("count", 0),
    )
    statuses = [str(item.get("status", "")).lower() for item in result.get("failed", [])]
    if "uncertain" in statuses:
        status = "uncertain"
    elif statuses:
        status = "failed"
    else:
        status = "completed"
    placement_guard.complete(
        user_id=current_user.user_id,
        idempotency_key=idempotency_key,
        status=status,
        result=response.model_dump(),
    )
    return response
