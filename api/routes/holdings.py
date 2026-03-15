from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse

from api.dependencies import JOB_HOLDINGS_ANALYZE, get_current_user, get_job_runner, get_session_registry
from api.errors import ServiceError
from api.schemas.common import JobQueuedResponse
from api.schemas.holdings import HoldingsAnalyzeRequest, HoldingsLatestResponse
from core.auth.context import UserContext
from core.runtime.job_runner import JobRunner
from core.runtime.session_registry import SessionRegistry


router = APIRouter(prefix="/holdings", tags=["holdings"])


@router.post("/analyze", response_model=JobQueuedResponse)
def analyze_holdings(
    payload: HoldingsAnalyzeRequest,
    job_runner: JobRunner = Depends(get_job_runner),
    registry: SessionRegistry = Depends(get_session_registry),
    current_user: UserContext = Depends(get_current_user),
):
    registry.require_access(payload.session_id, current_user)
    job_id = job_runner.start_job(
        session_id=payload.session_id,
        job_type=JOB_HOLDINGS_ANALYZE,
        payload={"filters": payload.filters or {}, "sort_by": payload.sort_by},
    )
    return JobQueuedResponse(job_id=job_id)


@router.get("/{session_id}/latest", response_model=HoldingsLatestResponse)
def holdings_latest(
    session_id: str,
    job_runner: JobRunner = Depends(get_job_runner),
    registry: SessionRegistry = Depends(get_session_registry),
    current_user: UserContext = Depends(get_current_user),
):
    registry.require_access(session_id, current_user)
    latest = job_runner.get_latest_result(
        session_id=session_id,
        job_type=JOB_HOLDINGS_ANALYZE,
        tenant_id=current_user.tenant_id,
    )
    if not latest:
        raise ServiceError("No holdings analysis found", error_code="no_results", http_status=404)
    return HoldingsLatestResponse(items=latest.get("items", []))


@router.get("/{session_id}/export")
def holdings_export(
    session_id: str,
    job_runner: JobRunner = Depends(get_job_runner),
    registry: SessionRegistry = Depends(get_session_registry),
    current_user: UserContext = Depends(get_current_user),
) -> Response:
    registry.require_access(session_id, current_user)
    latest = job_runner.get_latest_result(
        session_id=session_id,
        job_type=JOB_HOLDINGS_ANALYZE,
        tenant_id=current_user.tenant_id,
    )
    if not latest:
        raise ServiceError("No holdings analysis found", error_code="no_results", http_status=404)
    rows = latest.get("items", [])
    if not rows:
        raise ServiceError("No holdings data to export", error_code="no_data", http_status=404)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)

    safe_session = "".join(ch for ch in session_id if ch.isalnum()) or "session"
    filename = f"holdings_{safe_session}_{datetime.utcnow().date()}.csv"
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers=headers)
