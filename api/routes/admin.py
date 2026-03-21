"""Admin endpoints for user management and market data."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from api.dependencies import (
    JOB_CMP_REFRESH,
    JOB_OHLCV_REFRESH,
    JOB_SYMBOL_CATALOG_IMPORT,
    get_auth_service,
    get_job_runner,
    get_session_manager,
    get_symbol_catalog_service,
    require_admin,
)
from core.auth.active_connection_store import get_active_connection_store
from core.auth.context import UserContext
from core.runtime.job_runner import JobRunner
from core.services.auth_service import AuthService
from core.services.symbol_catalog_service import SymbolCatalogService
from core.session_manager import SessionManager

router = APIRouter(prefix="/admin", tags=["admin"])


class TradingEnabledRequest(BaseModel):
    enabled: bool


class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    trading_enabled: bool


@router.post("/users/{user_id}/trading-enabled", response_model=UserResponse)
def set_user_trading_enabled(
    user_id: int,
    payload: TradingEnabledRequest,
    current_user: UserContext = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Enable or disable trading for a user. Admin only."""
    try:
        user = auth_service.set_user_trading_enabled(
            user_id, payload.enabled, current_user.user_id
        )
        return UserResponse(
            id=user.id,
            email=user.email,
            role=user.role,
            trading_enabled=user.trading_enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    current_user: UserContext = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Get user details. Admin only."""
    user = auth_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        trading_enabled=user.trading_enabled,
    )


@router.post("/symbol-catalog/import")
async def import_symbol_catalog(
    file: UploadFile = File(...),
    current_user: UserContext = Depends(require_admin),
):
    """Upload CSV to import symbol catalog. Uses job framework."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    content = await file.read()
    try:
        csv_content = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded")

    from api.dependencies import get_job_runner

    job_runner = get_job_runner()
    job_id = job_runner.start_job(
        session_id=f"admin-{current_user.user_id}",
        job_type=JOB_SYMBOL_CATALOG_IMPORT,
        payload={
            "csv_content": csv_content,
            "filename": file.filename,
            "replace": True,
        },
    )
    return {"job_id": job_id}


@router.get("/symbol-catalog/status")
def get_symbol_catalog_status(
    current_user: UserContext = Depends(require_admin),
    service: SymbolCatalogService = Depends(get_symbol_catalog_service),
):
    """Get symbol catalog status. Admin only."""
    return service.get_status()


@router.post("/market-data/cmp/refresh")
def refresh_cmp(
    current_user: UserContext = Depends(require_admin),
    session_manager: SessionManager = Depends(get_session_manager),
):
    """Refresh CMP values from Upstox. Admin only."""
    from api.dependencies import get_job_runner
    from core.services.broker_connection_service import BrokerConnectionService

    broker_service = BrokerConnectionService()

    active_store = get_active_connection_store()
    connection_id = active_store.get_active_connection(current_user.user_id)

    if connection_id:
        connection = broker_service.get_connection(connection_id)
    else:
        connections = broker_service.list_connections(
            user_id=current_user.user_id,
        )
        upstox_conns = [c for c in connections if c.broker_name == "upstox"]
        connection = upstox_conns[0] if upstox_conns else None
        connection_id = connection.id if connection else None

    if not connection_id or not connection or connection.broker_name != "upstox":
        raise HTTPException(
            status_code=409,
            detail="UPSTOX_NOT_CONNECTED: No active Upstox connection found. Please connect Upstox from the Brokers page first.",
        )

    token_bundle = session_manager.get_token_bundle(
        "upstox", connection_id=connection_id
    )
    if not token_bundle:
        raise HTTPException(
            status_code=409,
            detail="UPSTOX_NOT_CONNECTED: Upstox session has expired. Please reconnect Upstox from the Brokers page.",
        )

    job_runner = get_job_runner()
    job_id = job_runner.start_job(
        session_id=f"admin-{current_user.user_id}",
        job_type=JOB_CMP_REFRESH,
        payload={
            "connection_id": connection_id,
        },
    )

    return {"job_id": job_id}


@router.get("/market-data/cmp/status")
def get_cmp_status(
    current_user: UserContext = Depends(require_admin),
    service: SymbolCatalogService = Depends(get_symbol_catalog_service),
    job_runner: JobRunner = Depends(get_job_runner),
):
    """Get CMP status including coverage stats and last job summary. Admin only."""
    status = service.get_status()

    import json

    from core.services.symbol_catalog_repository import SymbolCatalogRepository
    from db.database import SessionLocal
    from db.models import Job

    db = SessionLocal()
    try:
        repo = SymbolCatalogRepository(db)
        cmp_count = repo.get_cmp_count()

        latest_cmp_job = (
            db.query(Job)
            .filter(
                Job.job_type == JOB_CMP_REFRESH,
                Job.status.in_(["succeeded", "failed"]),
            )
            .order_by(Job.updated_at.desc())
            .first()
        )

        latest_job = None
        if latest_cmp_job:
            result = (
                json.loads(latest_cmp_job.result_json)
                if latest_cmp_job.result_json
                else {}
            )
            latest_job = {
                "job_id": latest_cmp_job.id,
                "processed": result.get("processed", 0),
                "succeeded": result.get("succeeded", 0),
                "failed": result.get("failed", 0),
                "updated_at": (
                    latest_cmp_job.updated_at.isoformat()
                    if latest_cmp_job.updated_at
                    else None
                ),
            }

        return {
            "total_symbols": status.get("total_symbols", 0),
            "cmp_present_count": cmp_count,
            "last_cmp_job": latest_job,
        }
    finally:
        db.close()


@router.get("/jobs/{job_id}/failures")
def get_job_failures(
    job_id: int,
    current_user: UserContext = Depends(require_admin),
    job_runner: JobRunner = Depends(get_job_runner),
):
    """Get failures for a job. Admin only."""
    try:
        return job_runner.get_job_failures(job_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/market-data/ohlcv/last-job")
def get_last_ohlcv_job(
    current_user: UserContext = Depends(require_admin),
):
    """Get the last OHLCV refresh job. Admin only."""
    import json

    from db.database import SessionLocal
    from db.models import Job

    db = SessionLocal()
    try:
        latest_job = (
            db.query(Job)
            .filter(
                Job.job_type == JOB_OHLCV_REFRESH,
                Job.status.in_(["pending", "running", "succeeded", "failed"]),
            )
            .order_by(Job.updated_at.desc())
            .first()
        )

        if not latest_job:
            return {"job_id": None, "status": "not_found"}

        result = json.loads(latest_job.result_json) if latest_job.result_json else {}
        return {
            "job_id": latest_job.id,
            "status": latest_job.status,
            "progress": latest_job.progress,
            "result": result,
            "created_at": (
                latest_job.created_at.isoformat() if latest_job.created_at else None
            ),
            "updated_at": (
                latest_job.updated_at.isoformat() if latest_job.updated_at else None
            ),
        }
    finally:
        db.close()


@router.get("/market-data/ohlcv/status")
def get_ohlcv_status(
    current_user: UserContext = Depends(require_admin),
):
    """Get OHLCV status including coverage stats and last job summary. Admin only."""
    import json

    from sqlalchemy import func

    from db.database import SessionLocal
    from db.models import Job, OhlcvDaily

    db = SessionLocal()
    try:
        total_candles = db.query(func.count(OhlcvDaily.symbol)).scalar() or 0
        symbols_with_candles = (
            db.query(func.count(func.distinct(OhlcvDaily.symbol))).scalar() or 0
        )

        latest_job = (
            db.query(Job)
            .filter(
                Job.job_type == JOB_OHLCV_REFRESH,
                Job.status.in_(["succeeded", "failed"]),
            )
            .order_by(Job.updated_at.desc())
            .first()
        )

        last_job_info = None
        if latest_job:
            result = (
                json.loads(latest_job.result_json) if latest_job.result_json else {}
            )
            last_job_info = {
                "job_id": latest_job.id,
                "processed_symbols": result.get("processed_symbols", 0),
                "succeeded_symbols": result.get("succeeded_symbols", 0),
                "failed_symbols": result.get("failed_symbols", 0),
                "days": result.get("days", 0),
                "updated_at": (
                    latest_job.updated_at.isoformat() if latest_job.updated_at else None
                ),
            }

        return {
            "total_candles": total_candles,
            "symbols_with_candles": symbols_with_candles,
            "last_ohlcv_job": last_job_info,
        }
    finally:
        db.close()


@router.post("/market-data/ohlcv/refresh")
def refresh_ohlcv(
    days: int = 200,
    current_user: UserContext = Depends(require_admin),
    session_manager: SessionManager = Depends(get_session_manager),
):
    """Refresh OHLCV data from Upstox. Admin only."""
    from api.dependencies import get_job_runner
    from core.services.broker_connection_service import BrokerConnectionService

    broker_service = BrokerConnectionService()

    active_store = get_active_connection_store()
    connection_id = active_store.get_active_connection(current_user.user_id)

    if connection_id:
        connection = broker_service.get_connection(connection_id)
    else:
        connections = broker_service.list_connections(
            user_id=current_user.user_id,
        )
        upstox_conns = [c for c in connections if c.broker_name == "upstox"]
        connection = upstox_conns[0] if upstox_conns else None
        connection_id = connection.id if connection else None

    if not connection_id or not connection or connection.broker_name != "upstox":
        raise HTTPException(
            status_code=409,
            detail="UPSTOX_NOT_CONNECTED: No active Upstox connection found. Please connect Upstox from the Brokers page first.",
        )

    token_bundle = session_manager.get_token_bundle(
        "upstox", connection_id=connection_id
    )
    if not token_bundle:
        raise HTTPException(
            status_code=409,
            detail="UPSTOX_NOT_CONNECTED: Upstox session has expired. Please reconnect Upstox from the Brokers page.",
        )

    job_runner = get_job_runner()
    job_id = job_runner.start_job(
        session_id=f"admin-{current_user.user_id}",
        job_type=JOB_OHLCV_REFRESH,
        payload={
            "connection_id": connection_id,
            "days": days,
        },
    )

    return {"job_id": job_id}
