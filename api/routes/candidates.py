"""API routes for the unified entry candidate pipeline."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from api.dependencies import (
    JOB_CANDIDATE_GENERATE,
    get_current_user,
    get_gtt_service,
    get_job_runner,
    get_session_registry,
    require_trading_enabled,
)
from api.errors import ServiceError
from api.schemas.candidates import (
    CandidateGenerateRequest,
    CandidatePlaceRequest,
    CandidatePlaceResponse,
    PlaceOrderResult,
)
from core.audit import log_audit
from core.auth.context import UserContext
from core.runtime.job_runner import JobRunner
from core.runtime.session_registry import SessionRegistry
from core.services.gtt_service import GTTService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.post("/generate")
def generate_candidates(
    payload: CandidateGenerateRequest,
    session_id: str | None = None,
    job_runner: JobRunner = Depends(get_job_runner),
    registry: SessionRegistry = Depends(get_session_registry),
    current_user: UserContext = Depends(get_current_user),
):
    """Queue candidate generation for a session."""
    if not session_id:
        raise ServiceError(
            "session_id is required",
            error_code="missing_session",
            http_status=400,
        )

    registry.require_access(session_id, current_user)

    job_id = job_runner.start_job(
        session_id=session_id,
        job_type=JOB_CANDIDATE_GENERATE,
        payload={
            "session_id": session_id,
            "apply_risk": payload.apply_risk_management,
        },
    )
    return {"job_id": job_id}


@router.get("/{session_id}/latest")
def latest_candidates(
    session_id: str,
    registry: SessionRegistry = Depends(get_session_registry),
    job_runner: JobRunner = Depends(get_job_runner),
    current_user: UserContext = Depends(get_current_user),
):
    """Return the most recent candidate generation result for a session."""
    registry.require_access(session_id, current_user)

    latest = job_runner.get_latest_result(
        session_id=session_id,
        job_type=JOB_CANDIDATE_GENERATE,
    )

    if not latest:
        raise ServiceError(
            "No candidates available. Run Generate Candidates first.",
            error_code="no_results",
            http_status=404,
        )

    return latest


@router.post("/{session_id}/place")
def place_candidates(
    session_id: str,
    payload: CandidatePlaceRequest,
    registry: SessionRegistry = Depends(get_session_registry),
    job_runner: JobRunner = Depends(get_job_runner),
    gtt_service: GTTService = Depends(get_gtt_service),
    current_user: UserContext = Depends(get_current_user),
):
    """Place GTT orders for selected candidate symbols."""
    require_trading_enabled(current_user)
    registry.require_access(session_id, current_user)

    log_audit(
        action="candidate_place_orders",
        user=current_user,
        resource_type="candidates",
        resource_id=session_id,
        metadata={"symbols": payload.symbols},
    )

    # Load latest candidate generation result
    latest = job_runner.get_latest_result(
        session_id=session_id,
        job_type=JOB_CANDIDATE_GENERATE,
    )
    if not latest:
        raise ServiceError(
            "No candidates available. Run Generate Candidates first.",
            error_code="no_results",
            http_status=404,
        )

    # Build GTT plan from selected candidates; keep a lookup for strategy info
    candidates = latest.get("candidates", [])
    symbol_set = {s.upper() for s in payload.symbols}
    plan: list[dict] = []
    info_by_symbol: dict[str, dict] = {}
    skipped_count = 0
    errors: list[str] = []

    for c in candidates:
        sym = c.get("symbol", "").upper()
        if sym not in symbol_set:
            continue
        if not c.get("is_selectable"):
            skipped_count += 1
            continue
        if c.get("side") != "BUY":
            skipped_count += 1
            continue
        if not c.get("order_price") or not c.get("trigger_price") or not c.get("qty"):
            skipped_count += 1
            errors.append(f"{sym}: Missing order price, trigger, or quantity")
            continue

        info_by_symbol[sym] = {
            "strategy_type": c.get("strategy_type", ""),
            "amount": c.get("amount", 0),
        }
        plan.append(
            {
                "symbol": c["symbol"],
                "exchange": c.get("exchange") or "NSE",
                "price": c["order_price"],
                "trigger": c["trigger_price"],
                "qty": c["qty"],
                "ltp": c.get("cmp") or 0,
            }
        )

    if not plan:
        return CandidatePlaceResponse(
            placed=0,
            skipped=skipped_count,
            errors=errors,
        )

    # Place orders via GTT service
    try:
        result = gtt_service.place_orders(session_id, plan, dry_run=False)
    except Exception as exc:
        raise ServiceError(str(exc), error_code="place_failed", http_status=500) from exc

    # Build per-order results enriched with strategy info
    broker_results = result.get("results", [])
    results: list[PlaceOrderResult] = []
    placed = 0
    failed_skipped = 0

    for r in broker_results:
        sym = r.get("symbol", "").upper()
        info = info_by_symbol.get(sym, {})
        status = r.get("status", "Fail")
        if status == "Success":
            placed += 1
        elif status == "Skipped":
            failed_skipped += 1

        order = next((o for o in plan if o["symbol"].upper() == sym), {})
        results.append(
            PlaceOrderResult(
                symbol=r.get("symbol", ""),
                strategy_type=info.get("strategy_type", ""),
                qty=order.get("qty", 0),
                order_price=r.get("price"),
                trigger_price=r.get("trigger"),
                amount=info.get("amount", 0),
                status=status,
                remarks=r.get("remarks", ""),
            )
        )

    for r in broker_results:
        if r.get("status") == "Fail":
            errors.append(f"{r.get('symbol', '?')}: {r.get('remarks', 'Unknown error')}")

    return CandidatePlaceResponse(
        placed=placed,
        skipped=skipped_count + failed_skipped,
        errors=errors,
        results=results,
    )
