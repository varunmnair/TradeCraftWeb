from __future__ import annotations

from fastapi import APIRouter, Depends

from api.dependencies import (
    JOB_GTT_APPLY,
    JOB_GTT_PREVIEW,
    get_confirm_token_service,
    get_current_user,
    get_gtt_service,
    get_job_runner,
    get_session_registry,
    require_trading_enabled,
)
from api.errors import ServiceError
from api.schemas.common import JobQueuedResponse
from api.schemas.gtt import GTTApplyRequest, GTTConfirmRequest, GTTConfirmResponse, GTTOrdersResponse, GTTPreviewRequest, GTTDeleteRequest, GTTDeleteResponse, GTTAdjustRequest, GTTAdjustResponse
from core.auth.context import UserContext
from core.runtime.job_runner import JobRunner
from core.runtime.session_registry import SessionRegistry
from core.security.confirm_token_store import ConfirmTokenStore
from core.services.gtt_service import GTTService
from core.audit import log_audit


router = APIRouter(prefix="/gtt", tags=["gtt"])


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
        raise ServiceError(str(exc), error_code="session_not_found", http_status=404) from exc


@router.post("/preview", response_model=JobQueuedResponse)
def preview_gtt(
    payload: GTTPreviewRequest,
    job_runner: JobRunner = Depends(get_job_runner),
    registry: SessionRegistry = Depends(get_session_registry),
    current_user: UserContext = Depends(get_current_user),
):
    require_trading_enabled(current_user)
    registry.require_access(payload.session_id, current_user)
    
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
):
    require_trading_enabled(current_user)
    registry.require_access(payload.session_id, current_user)
    
    log_audit(
        action="gtt_confirm",
        user=current_user,
        resource_type="gtt",
        resource_id=payload.session_id,
    )
    
    issued = confirm_store.issue(session_id=payload.session_id, user_id=current_user.user_id, payload=payload.plan)
    return GTTConfirmResponse(**issued)


@router.post("/apply", response_model=JobQueuedResponse)
def apply_gtt(
    payload: GTTApplyRequest,
    job_runner: JobRunner = Depends(get_job_runner),
    confirm_store: ConfirmTokenStore = Depends(get_confirm_token_service),
    registry: SessionRegistry = Depends(get_session_registry),
    current_user: UserContext = Depends(get_current_user),
):
    require_trading_enabled(current_user)
    registry.require_access(payload.session_id, current_user)
    
    try:
        confirm_store.verify(
            token=payload.confirmation_token,
            session_id=payload.session_id,
            user_id=current_user.user_id,
            payload=payload.plan,
        )
    except ValueError as exc:
        raise ServiceError(str(exc), error_code="invalid_token", http_status=400) from exc
    
    log_audit(
        action="gtt_apply",
        user=current_user,
        resource_type="gtt",
        resource_id=payload.session_id,
        metadata={"symbols": [p.get("symbol") for p in payload.plan if p.get("symbol")]},
    )
    
    job_id = job_runner.start_job(
        session_id=payload.session_id,
        job_type=JOB_GTT_APPLY,
        payload={"plan": payload.plan},
    )
    return JobQueuedResponse(job_id=job_id)


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
            deleted=result.get("deleted", []),
            count=len(result.get("deleted", []))
        )
    except Exception as exc:
        raise ServiceError(str(exc), error_code="delete_failed", http_status=500) from exc


@router.post("/adjust", response_model=GTTAdjustResponse)
def adjust_gtt_orders(
    payload: GTTAdjustRequest,
    service: GTTService = Depends(get_gtt_service),
    registry: SessionRegistry = Depends(get_session_registry),
    current_user: UserContext = Depends(get_current_user),
):
    require_trading_enabled(current_user)
    registry.require_access(payload.session_id, current_user)
    
    log_audit(
        action="gtt_adjust",
        user=current_user,
        resource_type="gtt",
        resource_id=payload.session_id,
        metadata={"order_ids": payload.order_ids, "target_variance": payload.target_variance},
    )
    
    try:
        result = service.adjust_orders_by_ids(
            payload.session_id, 
            payload.order_ids, 
            payload.target_variance
        )
        return GTTAdjustResponse(
            adjusted=result.get("adjusted", []),
            failed=result.get("failed", []),
            count=result.get("count", 0)
        )
    except Exception as exc:
        raise ServiceError(str(exc), error_code="adjust_failed", http_status=500) from exc
