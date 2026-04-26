"""Admin endpoints for user management and market data."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from api.dependencies import (
    JOB_OHLCV_REFRESH,
    JOB_OHLCV_REFRESH_SYMBOLS,
    JOB_SYMBOL_CATALOG_IMPORT,
    get_auth_service,
    get_global_cmp_manager,
    get_job_runner,
    get_session_manager,
    get_symbol_catalog_service,
    require_admin,
)
from core.auth.active_connection_store import get_active_connection_store
from core.auth.context import UserContext
from core.cmp import CMPManager
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


@router.get("/market-data/cmp/status")
def get_cmp_status(
    current_user: UserContext = Depends(require_admin),
):
    """Get CMP cache status. CMP is now served via in-memory cache with 5-min TTL."""
    import os

    cmp_manager = get_global_cmp_manager()
    cached_count = len(cmp_manager.cache)
    last_updated = (
        datetime.fromtimestamp(cmp_manager.last_updated, tz=timezone.utc).isoformat()
        if cmp_manager.last_updated > 0
        else None
    )
    ttl_seconds = cmp_manager.ttl
    has_analytics_token = bool(os.environ.get("UPSTOX_ANALYTICS_TOKEN"))

    return {
        "cached_symbols": cached_count,
        "last_updated": last_updated,
        "ttl_seconds": ttl_seconds,
        "has_analytics_token": has_analytics_token,
        "note": "CMP is fetched from Upstox API on-demand and cached in-memory with 5-min TTL",
    }


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

    from core.services.ohlcv_refresh_service import OhlcvRefreshService

    service = OhlcvRefreshService()
    config_days = service.get_config_days()

    db = SessionLocal()
    try:
        total_candles = db.query(func.count(OhlcvDaily.symbol)).scalar() or 0
        total_symbols = (
            db.query(func.count(func.distinct(OhlcvDaily.symbol))).scalar() or 0
        )

        min_date = db.query(func.min(OhlcvDaily.trade_date)).scalar()
        max_date = db.query(func.max(OhlcvDaily.trade_date)).scalar()

        latest_job = (
            db.query(Job)
            .filter(
                Job.job_type.in_([JOB_OHLCV_REFRESH, JOB_OHLCV_REFRESH_SYMBOLS]),
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
                "symbols_refreshed": result.get("symbols_refreshed", 0),
                "symbols_skipped": result.get("symbols_skipped", 0),
                "symbols_failed": result.get("symbols_failed", 0),
                "days": result.get("days", config_days),
                "updated_at": (
                    latest_job.updated_at.isoformat() if latest_job.updated_at else None
                ),
            }

        return {
            "config_days": config_days,
            "total_symbols": total_symbols,
            "date_from": min_date.isoformat() if min_date else None,
            "date_to": max_date.isoformat() if max_date else None,
            "total_candles": total_candles,
            "last_updated": latest_job.updated_at.isoformat() if latest_job else None,
            "last_ohlcv_job": last_job_info,
        }
    finally:
        db.close()


@router.get("/market-data/ohlcv/config")
def get_ohlcv_config(
    current_user: UserContext = Depends(require_admin),
):
    """Get OHLCV configuration. Admin only."""
    from core.services.ohlcv_refresh_service import OhlcvRefreshService

    service = OhlcvRefreshService()
    days = service.get_config_days()
    return {"days": days}


class OhlcvConfigUpdate(BaseModel):
    days: int = 200


@router.put("/market-data/ohlcv/config")
def update_ohlcv_config(
    config: OhlcvConfigUpdate,
    current_user: UserContext = Depends(require_admin),
):
    """Update OHLCV configuration. Admin only."""
    from core.services.ohlcv_refresh_service import OhlcvRefreshService

    if config.days < 30 or config.days > 500:
        raise HTTPException(
            status_code=400,
            detail="Days must be between 30 and 500",
        )

    service = OhlcvRefreshService()
    service.set_config_days(config.days)
    return {"days": config.days}


@router.post("/market-data/ohlcv/purge-all")
def purge_all_ohlcv(
    current_user: UserContext = Depends(require_admin),
):
    """Purge all OHLCV data. Admin only."""
    from core.services.ohlcv_refresh_service import OhlcvRefreshService

    service = OhlcvRefreshService()
    result = service.purge_all()
    return result


class PurgeSymbolsRequest(BaseModel):
    symbols: list[str]


@router.post("/market-data/ohlcv/purge-symbols")
def purge_symbols_ohlcv(
    request: PurgeSymbolsRequest,
    current_user: UserContext = Depends(require_admin),
):
    """Purge OHLCV data for specific symbols. Admin only."""
    from core.services.ohlcv_refresh_service import OhlcvRefreshService

    service = OhlcvRefreshService()
    result = service.purge_for_symbols(request.symbols)
    return result


@router.get("/market-data/ohlcv/inspect/{symbol}")
def inspect_ohlcv(
    symbol: str,
    days: int = 100,
    current_user: UserContext = Depends(require_admin),
):
    """Inspect OHLCV data for a specific symbol. Admin only."""
    from core.services.ohlcv_refresh_service import OhlcvRefreshService

    service = OhlcvRefreshService()
    result = service.inspect_symbol(symbol, days)
    return result


@router.post("/market-data/ohlcv/refresh")
def refresh_ohlcv(
    symbols: str = Query("", description="Comma-separated symbols to refresh"),
    days: int = Query(200, ge=1, le=500, description="Number of days to fetch"),
    current_user: UserContext = Depends(require_admin),
):
    """Refresh OHLCV data. Provide comma-separated symbols or leave empty to use existing. Admin only."""
    import os
    from api.dependencies import get_job_runner

    analytics_token = os.environ.get("UPSTOX_ANALYTICS_TOKEN")
    if not analytics_token:
        raise HTTPException(
            status_code=409,
            detail="UPSTOX_ANALYTICS_TOKEN not configured. Set UPSTOX_ANALYTICS_TOKEN in .env to refresh OHLCV data.",
        )

    from core.services.ohlcv_refresh_service import OhlcvRefreshService
    service = OhlcvRefreshService()

    # Parse symbols from comma-separated string
    symbol_list = []
    if symbols:
        symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    
    if not symbol_list:
        symbol_list = service.get_existing_symbols()

    if not symbol_list:
        return {
            "job_id": None,
            "message": "No symbols provided and no existing OHLCV data found. Please provide symbols.",
            "symbols_count": 0,
        }

    job_runner = get_job_runner()
    job_id = job_runner.start_job(
        session_id=f"admin-{current_user.user_id}",
        job_type=JOB_OHLCV_REFRESH_SYMBOLS,
        payload={
            "symbols": symbol_list,
            "days": days,
            "force_refresh": True,
        },
    )

    return {"job_id": job_id, "symbols_count": len(symbol_list)}
