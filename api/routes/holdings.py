from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.dependencies import (
    JOB_HOLDINGS_ANALYZE,
    get_current_user,
    get_job_runner,
    get_session_registry,
    get_trades_service,
)
from api.errors import ServiceError
from api.schemas.common import JobQueuedResponse
from api.schemas.holdings import HoldingsAnalyzeRequest, HoldingsLatestResponse
from core.auth.context import UserContext
from core.runtime.job_runner import JobRunner
from core.runtime.session_registry import SessionRegistry
from core.services.trades_service import TradesService

router = APIRouter(prefix="/holdings", tags=["holdings"])


class HoldingsReadinessResponse(BaseModel):
    broker: str
    market_data_ready: bool
    trades_ready: bool
    ready_to_analyze: bool
    blocking_reason: Optional[str]
    missing: dict


@router.get("/analyze/status", response_model=HoldingsReadinessResponse)
def holdings_analyze_status(
    session_id: str,
    current_user: UserContext = Depends(get_current_user),
    registry: SessionRegistry = Depends(get_session_registry),
    trades_service: TradesService = Depends(get_trades_service),
):
    """Check if holdings analysis is ready to run."""
    registry.require_access(session_id, current_user)
    context = registry.get_session(session_id)
    if not context:
        raise HTTPException(status_code=404, detail="Session not found")

    broker_name = context.broker_name
    holdings = context.session_cache.get_holdings()
    symbols = [
        h.get("tradingsymbol", "").upper() for h in holdings if h.get("tradingsymbol")
    ]

    if current_user.user_id is None:
        raise HTTPException(status_code=400, detail="User ID not found")

    return trades_service.get_readiness(
        user_id=current_user.user_id,
        broker=broker_name,
        holdings_symbols=symbols,
    )


@router.post("/analyze", response_model=JobQueuedResponse)
def analyze_holdings(
    payload: HoldingsAnalyzeRequest,
    job_runner: JobRunner = Depends(get_job_runner),
    registry: SessionRegistry = Depends(get_session_registry),
    current_user: UserContext = Depends(get_current_user),
):
    registry.require_access(payload.session_id, current_user)

    context = registry.get_session(payload.session_id)
    if not context:
        raise HTTPException(status_code=404, detail="Session not found")

    broker_name = context.broker_name
    holdings = context.session_cache.get_holdings()
    symbols = [
        h.get("tradingsymbol", "").upper() for h in holdings if h.get("tradingsymbol")
    ]

    if current_user.user_id is None:
        raise HTTPException(status_code=400, detail="User ID not found")

    trades_service = get_trades_service()
    readiness = trades_service.get_readiness(
        user_id=current_user.user_id,
        broker=broker_name,
        holdings_symbols=symbols,
    )

    if not readiness["ready_to_analyze"]:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "NOT_READY",
                "blocking_reason": readiness["blocking_reason"],
                "missing": readiness["missing"],
            },
        )

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
    )
    if not latest:
        raise ServiceError(
            "No holdings analysis found", error_code="no_results", http_status=404
        )
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
    )
    if not latest:
        raise ServiceError(
            "No holdings analysis found", error_code="no_results", http_status=404
        )
    rows = latest.get("items", [])
    if not rows:
        raise ServiceError(
            "No holdings data to export", error_code="no_data", http_status=404
        )

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)

    safe_session = "".join(ch for ch in session_id if ch.isalnum()) or "session"
    filename = f"holdings_{safe_session}_{datetime.utcnow().date()}.csv"
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return StreamingResponse(
        iter([output.getvalue()]), media_type="text/csv", headers=headers
    )
