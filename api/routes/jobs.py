from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_current_user, get_job_runner
from api.errors import ServiceError
from api.schemas.common import JobListResponse, JobStatus, JobStatusResponse
from core.auth.context import UserContext
from core.runtime.job_runner import JobRunner


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job(
    job_id: int,
    job_runner: JobRunner = Depends(get_job_runner),
    current_user: UserContext = Depends(get_current_user),
):
    try:
        job = job_runner.get_job(job_id)
    except ValueError as exc:
        raise ServiceError(str(exc), error_code="job_not_found", http_status=404) from exc
    tenant_id = current_user.tenant_id
    if tenant_id is not None and job.get("tenant_id") not in (tenant_id, None):
        raise ServiceError("Job not accessible", error_code="forbidden", http_status=403)
    return JobStatusResponse(job=JobStatus(**job))


@router.get("", response_model=JobListResponse)
def list_jobs(
    session_id: str | None = Query(default=None),
    job_runner: JobRunner = Depends(get_job_runner),
    current_user: UserContext = Depends(get_current_user),
):
    jobs = job_runner.list_jobs(session_id=session_id, tenant_id=current_user.tenant_id)
    return JobListResponse(jobs=[JobStatus(**job) for job in jobs])
