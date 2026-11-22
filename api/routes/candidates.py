"""API routes for the unified entry candidate pipeline."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, Header

from api.dependencies import (
    JOB_CANDIDATE_GENERATE,
    get_current_user,
    get_gtt_service,
    get_job_runner,
    get_placement_guard,
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
from core.services.placement_guard import (
    PlacementConflictError,
    PlacementContextError,
    PlacementGuardService,
    placement_error_code,
    resolve_idempotency_key,
    validate_placement_context,
)

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
    placement_guard: PlacementGuardService = Depends(get_placement_guard),
    current_user: UserContext = Depends(get_current_user),
    idempotency_header: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """Place GTT orders for selected candidate symbols with placement safety."""
    require_trading_enabled(current_user)
    if not current_user.user_id:
        raise ServiceError("User context missing", error_code="unauthorized", http_status=401)

    try:
        context = validate_placement_context(
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

    explicit_key = payload.idempotency_key or idempotency_header
    idempotency_key, fingerprint = resolve_idempotency_key(
        user_id=current_user.user_id,
        session_id=session_id,
        device_id=current_user.device_id,
        payload={"symbols": sorted(payload.symbols), "plan_scope": "candidate"},
        explicit_key=explicit_key,
    )

    log_audit(
        action="candidate_place_orders",
        user=current_user,
        resource_type="candidates",
        resource_id=session_id,
        metadata={
            "symbols": payload.symbols,
            "idempotency_key": idempotency_key,
            "broker_connection_id": context["broker_connection_id"],
        },
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
            idempotency_key=idempotency_key,
        )

    # Re-resolve with the concrete plan so a replay with a different plan is
    # rejected even when the client reuses a key.
    idempotency_key, fingerprint = resolve_idempotency_key(
        user_id=current_user.user_id,
        session_id=session_id,
        device_id=current_user.device_id,
        payload={
            "scope": "candidate",
            "symbols": sorted(payload.symbols),
            "plan": plan,
            "broker_connection_id": context["broker_connection_id"],
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
        replayed = stored.get("response")
        if replayed:
            response = CandidatePlaceResponse(**replayed)
            response.replayed = True
            return response
        return CandidatePlaceResponse(
            idempotency_key=idempotency_key,
            replayed=True,
            results=[
                PlaceOrderResult(**item) for item in stored.get("results", [])
            ],
        )

    # Place orders via GTT service
    try:
        result = gtt_service.place_orders(session_id, plan, dry_run=False)
    except Exception as exc:
        placement_guard.complete(
            user_id=current_user.user_id,
            idempotency_key=idempotency_key,
            status="failed",
            error=str(exc),
        )
        raise ServiceError(str(exc), error_code="place_failed", http_status=500) from exc

    # Build per-order results enriched with strategy info
    broker_results = result.get("results", [])
    results: list[PlaceOrderResult] = []
    placed = 0
    failed_skipped = 0
    uncertain_count = 0

    for r in broker_results:
        sym = r.get("symbol", "").upper()
        info = info_by_symbol.get(sym, {})
        status = r.get("status", "Fail")
        if status == "Success":
            placed += 1
        elif status == "Skipped":
            failed_skipped += 1
        elif status == "Uncertain":
            uncertain_count += 1

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
                order_id=r.get("order_id"),
                broker=context["broker_name"],
                broker_connection_id=context["broker_connection_id"],
            )
        )

    for r in broker_results:
        status = r.get("status")
        if status in {"Fail", "Uncertain"}:
            prefix = (
                "VERIFY IN BROKER APP - " if status == "Uncertain" else ""
            )
            errors.append(
                f"{r.get('symbol', '?')}: {prefix}{r.get('remarks', 'Unknown error')}"
            )

    response = CandidatePlaceResponse(
        placed=placed,
        skipped=skipped_count + failed_skipped,
        errors=errors,
        results=results,
        uncertain=uncertain_count,
        idempotency_key=idempotency_key,
    )
    statuses = [r.status.lower() for r in results]
    if uncertain_count:
        placement_status = "uncertain"
    elif any(s in {"fail", "failed"} for s in statuses):
        placement_status = "failed"
    else:
        placement_status = "completed"
    placement_guard.complete(
        user_id=current_user.user_id,
        idempotency_key=idempotency_key,
        status=placement_status,
        result={
            "results": result.get("results", []),
            "response": response.model_dump(),
        },
    )
    return response
