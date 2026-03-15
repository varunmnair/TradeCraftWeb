from __future__ import annotations

from fastapi import APIRouter, Depends

from api.dependencies import JOB_PLAN_GENERATE, JOB_DYNAMIC_AVG_GENERATE, get_current_user, get_job_runner, get_session_registry, get_entry_plan_service
from api.errors import ServiceError
from api.schemas.common import JobQueuedResponse
from api.schemas.plan import PlanGenerateRequest, PlanLatestResponse, DynamicAvgGenerateRequest
from core.auth.context import UserContext
from core.runtime.job_runner import JobRunner
from core.runtime.session_registry import SessionRegistry
from core.services.entry_plan_service import EntryPlanService


router = APIRouter(prefix="/plan", tags=["plan"])


@router.get("/{session_id}/entry-levels")
def list_entry_levels(
    session_id: str,
    registry: SessionRegistry = Depends(get_session_registry),
    entry_service: EntryPlanService = Depends(get_entry_plan_service),
    current_user: UserContext = Depends(get_current_user),
):
    """List entry levels for a session - useful for debugging DB vs CSV loading."""
    registry.require_access(session_id, current_user)
    return entry_service.list_entry_levels(session_id)


@router.post("/generate", response_model=JobQueuedResponse)
def generate_plan(
    payload: PlanGenerateRequest,
    job_runner: JobRunner = Depends(get_job_runner),
    registry: SessionRegistry = Depends(get_session_registry),
    current_user: UserContext = Depends(get_current_user),
):
    registry.require_access(payload.session_id, current_user)
    job_id = job_runner.start_job(
        session_id=payload.session_id,
        job_type=JOB_PLAN_GENERATE,
        payload={"apply_risk": payload.apply_risk},
    )
    return JobQueuedResponse(job_id=job_id)


@router.get("/{session_id}/latest", response_model=PlanLatestResponse)
def latest_plan(
    session_id: str,
    job_runner: JobRunner = Depends(get_job_runner),
    registry: SessionRegistry = Depends(get_session_registry),
    current_user: UserContext = Depends(get_current_user),
):
    registry.require_access(session_id, current_user)
    latest = job_runner.get_latest_result(
        session_id=session_id,
        job_type=JOB_PLAN_GENERATE,
        tenant_id=current_user.tenant_id,
    )
    if not latest:
        raise ServiceError("No plan available", error_code="no_results", http_status=404)
    return PlanLatestResponse(
        plan=latest.get("plan", []),
        skipped=latest.get("skipped", []),
    )


dynamic_avg_router = APIRouter(prefix="/dynamic-avg", tags=["dynamic-avg"])


@dynamic_avg_router.post("/generate", response_model=JobQueuedResponse)
def generate_dynamic_avg_plan(
    payload: DynamicAvgGenerateRequest,
    job_runner: JobRunner = Depends(get_job_runner),
    registry: SessionRegistry = Depends(get_session_registry),
    current_user: UserContext = Depends(get_current_user),
):
    registry.require_access(payload.session_id, current_user)
    job_id = job_runner.start_job(
        session_id=payload.session_id,
        job_type=JOB_DYNAMIC_AVG_GENERATE,
        payload={},
    )
    return JobQueuedResponse(job_id=job_id)


@dynamic_avg_router.get("/{session_id}/latest", response_model=PlanLatestResponse)
def latest_dynamic_avg_plan(
    session_id: str,
    job_runner: JobRunner = Depends(get_job_runner),
    registry: SessionRegistry = Depends(get_session_registry),
    current_user: UserContext = Depends(get_current_user),
):
    registry.require_access(session_id, current_user)
    latest = job_runner.get_latest_result(
        session_id=session_id,
        job_type=JOB_DYNAMIC_AVG_GENERATE,
        tenant_id=current_user.tenant_id,
    )
    if not latest:
        raise ServiceError("No dynamic averaging plan available", error_code="no_results", http_status=404)
    return PlanLatestResponse(
        plan=latest.get("plan", []),
        skipped=latest.get("skipped", []),
    )
