from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.dependencies import (
    JOB_DYNAMIC_AVG_GENERATE,
    JOB_PLAN_GENERATE,
    get_current_user,
    get_entry_plan_service,
    get_job_runner,
    get_session_registry,
)
from api.errors import ServiceError
from api.schemas.common import JobQueuedResponse
from api.schemas.plan import (
    DynamicAvgGenerateRequest,
    EntriesLatestResponse,
    PlanGenerateRequest,
)
from core.auth.context import UserContext
from core.runtime.job_runner import JobRunner
from core.runtime.session_registry import SessionRegistry
from core.services.entry_plan_service import (
    EntryPlanService,
    STRATEGY_TYPE_DYNAMIC_AVERAGING,
    STRATEGY_TYPE_MULTI_LEVEL,
)

router = APIRouter(prefix="/entries", tags=["entries"])


@router.get("/{session_id}/entry-levels")
def list_entry_levels(
    session_id: str,
    registry: SessionRegistry = Depends(get_session_registry),
    entry_service: EntryPlanService = Depends(get_entry_plan_service),
    current_user: UserContext = Depends(get_current_user),
):
    registry.require_access(session_id, current_user)
    return entry_service.list_entry_levels(session_id)


@router.post("/multi-level/generate", response_model=JobQueuedResponse)
def generate_multi_level_plan(
    payload: PlanGenerateRequest,
    job_runner: JobRunner = Depends(get_job_runner),
    registry: SessionRegistry = Depends(get_session_registry),
    current_user: UserContext = Depends(get_current_user),
):
    registry.require_access(payload.session_id, current_user)
    job_id = job_runner.start_job(
        session_id=payload.session_id,
        job_type=JOB_PLAN_GENERATE,
        payload={"strategy_type": STRATEGY_TYPE_MULTI_LEVEL, "apply_risk": payload.apply_risk},
    )
    return JobQueuedResponse(job_id=job_id)


@router.get("/multi-level/{session_id}/latest", response_model=EntriesLatestResponse)
def latest_multi_level_plan(
    session_id: str,
    registry: SessionRegistry = Depends(get_session_registry),
    job_runner: JobRunner = Depends(get_job_runner),
    current_user: UserContext = Depends(get_current_user),
):
    registry.require_access(session_id, current_user)
    latest = job_runner.get_latest_result(
        session_id=session_id,
        job_type=JOB_PLAN_GENERATE,
    )
    if not latest:
        raise ServiceError(
            "No multi-level plan available", error_code="no_results", http_status=404
        )
    return EntriesLatestResponse(
        strategy_type=STRATEGY_TYPE_MULTI_LEVEL,
        plan=latest.get("plan", []),
        skipped=latest.get("skipped", []),
    )


@router.post("/dynamic-averaging/generate", response_model=JobQueuedResponse)
def generate_dynamic_averaging_plan(
    payload: DynamicAvgGenerateRequest,
    job_runner: JobRunner = Depends(get_job_runner),
    registry: SessionRegistry = Depends(get_session_registry),
    current_user: UserContext = Depends(get_current_user),
):
    registry.require_access(payload.session_id, current_user)
    job_id = job_runner.start_job(
        session_id=payload.session_id,
        job_type=JOB_DYNAMIC_AVG_GENERATE,
        payload={"strategy_type": STRATEGY_TYPE_DYNAMIC_AVERAGING},
    )
    return JobQueuedResponse(job_id=job_id)


@router.get("/dynamic-averaging/{session_id}/latest", response_model=EntriesLatestResponse)
def latest_dynamic_averaging_plan(
    session_id: str,
    registry: SessionRegistry = Depends(get_session_registry),
    job_runner: JobRunner = Depends(get_job_runner),
    current_user: UserContext = Depends(get_current_user),
):
    registry.require_access(session_id, current_user)
    latest = job_runner.get_latest_result(
        session_id=session_id,
        job_type=JOB_DYNAMIC_AVG_GENERATE,
    )
    if not latest:
        raise ServiceError(
            "No dynamic averaging plan available",
            error_code="no_results",
            http_status=404,
        )
    return EntriesLatestResponse(
        strategy_type=STRATEGY_TYPE_DYNAMIC_AVERAGING,
        plan=latest.get("plan", []),
        skipped=latest.get("skipped", []),
    )


@router.delete("/purge")
def purge_plans(
    session_id: str,
    strategy_type: str = Query(None, description="Optional: filter by strategy type (multi_level or dynamic_averaging)"),
    entry_service: EntryPlanService = Depends(get_entry_plan_service),
    registry: SessionRegistry = Depends(get_session_registry),
    current_user: UserContext = Depends(get_current_user),
):
    registry.require_access(session_id, current_user)
    result = entry_service.purge_plans(session_id, strategy_type)
    return result


plan_router = APIRouter(prefix="/plan", tags=["plan"])


@plan_router.post("/generate", response_model=JobQueuedResponse)
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
        payload={"strategy_type": STRATEGY_TYPE_MULTI_LEVEL, "apply_risk": payload.apply_risk},
    )
    return JobQueuedResponse(job_id=job_id)


@plan_router.get("/{session_id}/latest", response_model=EntriesLatestResponse)
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
    )
    if not latest:
        raise ServiceError(
            "No plan available", error_code="no_results", http_status=404
        )
    return EntriesLatestResponse(
        strategy_type=STRATEGY_TYPE_MULTI_LEVEL,
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
        payload={"strategy_type": STRATEGY_TYPE_DYNAMIC_AVERAGING},
    )
    return JobQueuedResponse(job_id=job_id)


@dynamic_avg_router.get("/{session_id}/latest", response_model=EntriesLatestResponse)
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
    )
    if not latest:
        raise ServiceError(
            "No dynamic averaging plan available",
            error_code="no_results",
            http_status=404,
        )
    return EntriesLatestResponse(
        strategy_type=STRATEGY_TYPE_DYNAMIC_AVERAGING,
        plan=latest.get("plan", []),
        skipped=latest.get("skipped", []),
    )
