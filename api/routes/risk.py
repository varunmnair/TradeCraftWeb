from __future__ import annotations

from fastapi import APIRouter, Depends

from api.dependencies import (
    JOB_RISK_APPLY,
    get_current_user,
    get_job_runner,
    get_session_registry,
)
from api.errors import ServiceError
from api.schemas.common import JobQueuedResponse
from api.schemas.plan import PlanLatestResponse
from api.schemas.risk import RiskApplyRequest
from core.auth.context import UserContext
from core.runtime.job_runner import JobRunner
from core.runtime.session_registry import SessionRegistry

router = APIRouter(prefix="/risk", tags=["risk"])


@router.post("/apply", response_model=JobQueuedResponse)
def apply_risk(
    payload: RiskApplyRequest,
    job_runner: JobRunner = Depends(get_job_runner),
    registry: SessionRegistry = Depends(get_session_registry),
    current_user: UserContext = Depends(get_current_user),
):
    registry.require_access(payload.session_id, current_user)
    job_id = job_runner.start_job(
        session_id=payload.session_id,
        job_type=JOB_RISK_APPLY,
        payload={"plan": payload.plan},
    )
    return JobQueuedResponse(job_id=job_id)


@router.get("/{session_id}/latest", response_model=PlanLatestResponse)
def latest_risk_plan(
    session_id: str,
    job_runner: JobRunner = Depends(get_job_runner),
    registry: SessionRegistry = Depends(get_session_registry),
    current_user: UserContext = Depends(get_current_user),
):
    registry.require_access(session_id, current_user)
    latest = job_runner.get_latest_result(
        session_id=session_id,
        job_type=JOB_RISK_APPLY,
    )
    if not latest:
        raise ServiceError(
            "No risk-adjusted plan available", error_code="no_results", http_status=404
        )
    return PlanLatestResponse(
        strategy_type="multi_level",
        plan=latest.get("plan", []),
        skipped=latest.get("skipped", []),
    )
