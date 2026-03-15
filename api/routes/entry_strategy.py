from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from api.dependencies import get_current_user, get_db_session, get_session_registry
from api.errors import ServiceError
from api.schemas.entry_strategy import (
    EntryLevelSchema,
    EntryStrategyCSVRow,
    EntryStrategyFullSchema,
    EntryStrategyListResponse,
    EntryStrategySummarySchema,
    EntryStrategyUploadResponse,
    SuggestedRevision,
    SuggestRevisionResponse,
    ApplyRevisionRequest,
    ApplyRevisionResponse,
    UploadHistoryResponse,
    UploadHistoryItem,
    VersionListResponse,
    VersionItem,
    RestoreVersionRequest,
    RestoreVersionResponse,
    BulkSuggestRevisionRequest,
    BulkSuggestRevisionResponse,
    BulkSuggestRevisionItem,
    BulkApplyRevisionRequest,
    BulkApplyRevisionResponse,
    BulkApplyRevisionResult,
)
from core.auth.context import UserContext
from core.runtime.session_registry import SessionRegistry
from db.database import SessionLocal
from db.models import EntryLevel, EntryStrategy, EntryStrategyUpload, EntryStrategyVersion


router = APIRouter(prefix="/entry-strategies", tags=["entry-strategies"])


def _compute_averaging_rules_summary(rules_json: str | None) -> str | None:
    """Compute a human-readable summary from averaging_rules_json."""
    if not rules_json:
        return None
    try:
        rules = json.loads(rules_json)
        legs = rules.get("legs", "?")
        buyback = rules.get("buyback", [])
        trigger = rules.get("trigger_offset", "?")
        return f"{legs} legs, buyback {buyback}, offset {trigger}"
    except (json.JSONDecodeError, TypeError):
        return None


def get_db():
    yield from get_db_session()


def _get_broker_scope_from_session(
    session_id: str,
    registry: SessionRegistry,
    current_user: UserContext,
) -> tuple[str, str]:
    """Get broker and broker_user_id from active session."""
    context = registry.get_session(session_id)
    if not context:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    # Verify session belongs to current user
    if current_user.tenant_id and context.tenant_id and current_user.tenant_id != context.tenant_id:
        raise HTTPException(status_code=403, detail="Session does not belong to this tenant")
    if not current_user.is_dev and context.user_record_id and current_user.user_id != context.user_record_id:
        raise HTTPException(status_code=403, detail="Session owned by another user")
    
    broker = context.broker_name
    broker_user_id = context.user_id  # This is the broker_user_id (e.g., '32ADGT')
    
    return broker, broker_user_id


@router.get("", response_model=EntryStrategyListResponse)
def list_entry_strategies(
    session_id: str = Query(..., description="Active session ID to scope the strategies"),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
    registry: SessionRegistry = Depends(get_session_registry),
):
    """List entry strategies scoped to the active session (broker + broker_user_id)."""
    broker, broker_user_id = _get_broker_scope_from_session(session_id, registry, current_user)
    
    strategies = (
        db.query(EntryStrategy)
        .filter(
            EntryStrategy.tenant_id == current_user.tenant_id,
            EntryStrategy.user_id == current_user.user_id,
            EntryStrategy.broker == broker,
            EntryStrategy.broker_user_id == broker_user_id,
        )
        .all()
    )

    result = []
    for s in strategies:
        levels = (
            db.query(EntryLevel)
            .filter(EntryLevel.strategy_id == s.id)
            .filter(EntryLevel.is_active.is_(True))
            .order_by(EntryLevel.level_no)
            .all()
        )

        entry1 = None
        entry2 = None
        entry3 = None
        for level in levels:
            if level.level_no == 1:
                entry1 = level.price
            elif level.level_no == 2:
                entry2 = level.price
            elif level.level_no == 3:
                entry3 = level.price

        da_legs = None
        da_e1_buyback = None
        da_e2_buyback = None
        da_e3_buyback = None
        da_trigger_offset = None
        if s.averaging_rules_json:
            try:
                rules = json.loads(s.averaging_rules_json)
                da_legs = rules.get("legs")
                buyback = rules.get("buyback", [])
                da_trigger_offset = rules.get("trigger_offset")
                if len(buyback) >= 1:
                    da_e1_buyback = buyback[0]
                if len(buyback) >= 2:
                    da_e2_buyback = buyback[1]
                if len(buyback) >= 3:
                    da_e3_buyback = buyback[2]
            except (json.JSONDecodeError, TypeError):
                pass

        result.append(
            EntryStrategySummarySchema(
                symbol=s.symbol,
                allocated=s.allocated,
                quality=s.quality,
                exchange=s.exchange,
                entry1=entry1,
                entry2=entry2,
                entry3=entry3,
                da_enabled=s.dynamic_averaging_enabled,
                da_legs=da_legs,
                da_e1_buyback=da_e1_buyback,
                da_e2_buyback=da_e2_buyback,
                da_e3_buyback=da_e3_buyback,
                da_trigger_offset=da_trigger_offset,
                levels_count=len(levels),
                updated_at=s.updated_at,
            )
        )

    return EntryStrategyListResponse(strategies=result)


@router.delete("/{symbol}")
def delete_entry_strategy(
    symbol: str,
    session_id: str = Query(..., description="Active session ID to scope the strategies"),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
    registry: SessionRegistry = Depends(get_session_registry),
):
    """Delete a single entry strategy by symbol, scoped to the active session."""
    broker, broker_user_id = _get_broker_scope_from_session(session_id, registry, current_user)
    
    strategy = (
        db.query(EntryStrategy)
        .filter(
            EntryStrategy.tenant_id == current_user.tenant_id,
            EntryStrategy.user_id == current_user.user_id,
            EntryStrategy.broker == broker,
            EntryStrategy.broker_user_id == broker_user_id,
            EntryStrategy.symbol == symbol.upper(),
        )
        .first()
    )

    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    db.delete(strategy)
    db.commit()

    return {"deleted": symbol.upper(), "success": True}


@router.post("/bulk-delete")
def bulk_delete_entry_strategies(
    symbols: list[str],
    session_id: str = Query(..., description="Active session ID to scope the strategies"),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
    registry: SessionRegistry = Depends(get_session_registry),
):
    """Delete multiple entry strategies by symbols, scoped to the active session."""
    broker, broker_user_id = _get_broker_scope_from_session(session_id, registry, current_user)
    
    deleted_count = 0
    not_found = []
    
    for symbol in symbols:
        strategy = (
            db.query(EntryStrategy)
            .filter(
                EntryStrategy.tenant_id == current_user.tenant_id,
                EntryStrategy.user_id == current_user.user_id,
                EntryStrategy.broker == broker,
                EntryStrategy.broker_user_id == broker_user_id,
                EntryStrategy.symbol == symbol.upper(),
            )
            .first()
        )
        
        if strategy:
            db.delete(strategy)
            deleted_count += 1
        else:
            not_found.append(symbol)
    
    db.commit()
    
    return {
        "deleted_count": deleted_count,
        "not_found": not_found,
        "success": True,
    }


@router.get("/{symbol}", response_model=EntryStrategyFullSchema)
def get_entry_strategy(
    symbol: str,
    session_id: str = Query(..., description="Active session ID to scope the strategies"),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
    registry: SessionRegistry = Depends(get_session_registry),
):
    """Get a single entry strategy, scoped to the active session."""
    broker, broker_user_id = _get_broker_scope_from_session(session_id, registry, current_user)
    
    strategy = (
        db.query(EntryStrategy)
        .filter(
            EntryStrategy.tenant_id == current_user.tenant_id,
            EntryStrategy.user_id == current_user.user_id,
            EntryStrategy.broker == broker,
            EntryStrategy.broker_user_id == broker_user_id,
            EntryStrategy.symbol == symbol.upper(),
        )
        .first()
    )

    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    levels = (
        db.query(EntryLevel)
        .filter(EntryLevel.strategy_id == strategy.id)
        .order_by(EntryLevel.level_no)
        .all()
    )

    return EntryStrategyFullSchema(
        id=strategy.id,
        symbol=strategy.symbol,
        allocated=strategy.allocated,
        quality=strategy.quality,
        exchange=strategy.exchange,
        dynamic_averaging_enabled=strategy.dynamic_averaging_enabled,
        averaging_rules_json=strategy.averaging_rules_json,
        averaging_rules_summary=_compute_averaging_rules_summary(strategy.averaging_rules_json),
        levels=[
            EntryLevelSchema(
                id=l.id,
                level_no=l.level_no,
                price=l.price,
                is_active=l.is_active,
            )
            for l in levels
        ],
        created_at=strategy.created_at,
        updated_at=strategy.updated_at,
    )


@router.post("/upload-csv", response_model=EntryStrategyUploadResponse)
async def upload_csv(
    file: UploadFile = File(...),
    session_id: str = Query(..., description="Active session ID to scope the strategies"),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
    registry: SessionRegistry = Depends(get_session_registry),
):
    """Upload CSV to create/update entry strategies, scoped to the active session."""
    broker, broker_user_id = _get_broker_scope_from_session(session_id, registry, current_user)
    
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    content = await file.read()
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid UTF-8 encoding")

    reader = csv.DictReader(io.StringIO(text_content))
    field_names = [fn.strip() for fn in reader.fieldnames or []]

    # Map column names (handle spaces like "DA Enabled" -> "DA Enabled")
    has_entry_format = any(fn in field_names for fn in ["entry1", "entry2", "entry3"])
    has_level_format = "level_no" in field_names and "price" in field_names

    # Build lookup for normalized column names
    col_lookup = {}
    for fn in field_names:
        key = fn.strip().lower().replace(" ", "_")
        col_lookup[key] = fn
        col_lookup[fn.lower()] = fn
        col_lookup[fn] = fn

    has_entry_format = any(fn in field_names for fn in ["entry1", "entry2", "entry3"])
    has_level_format = "level_no" in field_names and "price" in field_names

    if has_entry_format:
        required_fields = {"symbol", "entry1"}
        if not required_fields.issubset(field_names):
            missing = required_fields - set(field_names)
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns: {', '.join(missing)}",
            )
    elif has_level_format:
        required_fields = {"symbol", "level_no", "price"}
        if not required_fields.issubset(field_names):
            missing = required_fields - set(field_names)
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns: {', '.join(missing)}",
            )
    else:
        raise HTTPException(
            status_code=400,
            detail="CSV must have either entry1/entry2/entry3 columns or level_no/price columns",
        )

    parsed_strategies: dict[str, dict[str, Any]] = {}
    row_errors: list[dict[str, Any]] = []

    # Helper to get column value by trying multiple possible column names
    def get_col(row: dict, *names: str) -> str:
        for name in names:
            if name in row:
                return row[name]
            # Try normalized version
            normalized = name.lower().replace(" ", "_")
            for k, v in row.items():
                if k.lower().replace(" ", "_") == normalized:
                    return v
        return ""

    for row_num, row in enumerate(reader, start=2):
        try:
            row = {k.strip(): (v.strip() if v else "") for k, v in row.items()}
            
            # Get symbol - prefer "symbol" column, fall back to "Raw Symbol"
            symbol = get_col(row, "symbol", "raw symbol", "Raw Symbol") or ""
            if symbol.startswith("nse:") or symbol.startswith("bse:"):
                symbol = symbol.split(":")[-1]
            symbol = symbol.upper().strip()

            if not symbol:
                row_errors.append({"row": row_num, "error": "symbol is empty"})
                continue

            if symbol not in parsed_strategies:
                allocated_val = get_col(row, "allocated", "Allocated")
                allocated = None
                if allocated_val:
                    try:
                        allocated = float(allocated_val)
                    except ValueError:
                        pass

                quality = get_col(row, "quality", "Quality") or None
                exchange = get_col(row, "exchange", "Exchange") or "NSE"

                da_enabled_str = get_col(row, "da_enabled", "DA Enabled", "da enabled").lower()
                da_enabled = da_enabled_str in ("y", "yes", "true", "1")
                
                da_legs_str = get_col(row, "da_legs", "DA legs", "da legs")
                da_legs = int(da_legs_str) if da_legs_str.isdigit() else (1 if da_enabled else 0)
                
                e1_buyback = get_col(row, "da_e1_buyback", "DA E1 Buyback", "da e1 buyback") or "0"
                e2_buyback = get_col(row, "da_e2_buyback", "DA E2 Buyback", "da e2 buyback") or "0"
                e3_buyback = get_col(row, "da_e3_buyback", "DA E3 Buyback", "da e3 buyback") or "0"
                trigger_offset = get_col(row, "datrigger_offset", "DATriggerOffset", "datrigger offset") or "0"

                averaging_rules = None
                if da_enabled:
                    try:
                        buyback = [
                            int(e1_buyback) if e1_buyback.isdigit() else 0,
                            int(e2_buyback) if e2_buyback.isdigit() else 0,
                            int(e3_buyback) if e3_buyback.isdigit() else 0,
                        ]
                        averaging_rules = json.dumps({
                            "legs": da_legs,
                            "buyback": buyback,
                            "trigger_offset": int(trigger_offset) if trigger_offset.isdigit() else 0,
                        })
                    except (ValueError, TypeError):
                        pass

                parsed_strategies[symbol] = {
                    "symbol": symbol,
                    "allocated": allocated,
                    "quality": quality,
                    "exchange": exchange,
                    "dynamic_averaging_enabled": da_enabled,
                    "averaging_rules_json": averaging_rules,
                    "levels": {},
                }

            if has_entry_format:
                for level_num in [1, 2, 3]:
                    entry_key = f"entry{level_num}"
                    price_str = row.get(entry_key, "").strip()
                    if price_str:
                        try:
                            price = float(price_str)
                            parsed_strategies[symbol]["levels"][level_num] = price
                        except ValueError:
                            pass
            else:
                level_no_str = row.get("level_no", "")
                price_str = row.get("price", "")
                if level_no_str and price_str:
                    try:
                        level_no = int(level_no_str)
                        price = float(price_str)
                        parsed_strategies[symbol]["levels"][level_no] = price
                    except ValueError:
                        pass

        except Exception as e:
            row_errors.append({"row": row_num, "error": str(e)})

    if not parsed_strategies and not row_errors:
        raise HTTPException(status_code=400, detail="CSV file is empty")

    if not parsed_strategies and not row_errors:
        raise HTTPException(status_code=400, detail="CSV file is empty")

    symbols_processed = set(parsed_strategies.keys())
    created_count = 0
    updated_count = 0
    now = datetime.utcnow()

    for symbol, strategy_data in parsed_strategies.items():
        levels_dict = strategy_data["levels"]

        existing = (
            db.query(EntryStrategy)
            .filter(
                EntryStrategy.tenant_id == current_user.tenant_id,
                EntryStrategy.user_id == current_user.user_id,
                EntryStrategy.broker == broker,
                EntryStrategy.broker_user_id == broker_user_id,
                EntryStrategy.symbol == symbol,
            )
            .first()
        )

        if existing:
            existing.allocated = strategy_data.get("allocated")
            existing.quality = strategy_data.get("quality")
            existing.exchange = strategy_data.get("exchange", "NSE")
            existing.dynamic_averaging_enabled = strategy_data.get("dynamic_averaging_enabled", False)
            existing.averaging_rules_json = strategy_data.get("averaging_rules_json")
            existing.updated_at = now

            old_levels = db.query(EntryLevel).filter(EntryLevel.strategy_id == existing.id).all()
            if old_levels:
                _create_version(
                    db=db,
                    strategy=existing,
                    action="upload",
                    changes_summary=f"CSV upload: {len(levels_dict)} levels",
                    levels=old_levels,
                )

            db.query(EntryLevel).filter(EntryLevel.strategy_id == existing.id).delete()

            for level_no, price in levels_dict.items():
                db.add(EntryLevel(
                    strategy_id=existing.id,
                    level_no=level_no,
                    price=price,
                    is_active=True,
                ))
            updated_count += 1
        else:
            new_strategy = EntryStrategy(
                tenant_id=current_user.tenant_id,
                user_id=current_user.user_id,
                symbol=symbol,
                broker=broker,
                broker_user_id=broker_user_id,
                allocated=strategy_data.get("allocated"),
                quality=strategy_data.get("quality"),
                exchange=strategy_data.get("exchange", "NSE"),
                dynamic_averaging_enabled=strategy_data.get("dynamic_averaging_enabled", False),
                averaging_rules_json=strategy_data.get("averaging_rules_json"),
                created_at=now,
                updated_at=now,
            )
            db.add(new_strategy)
            db.flush()

            for level_no, price in levels_dict.items():
                db.add(EntryLevel(
                    strategy_id=new_strategy.id,
                    level_no=level_no,
                    price=price,
                    is_active=True,
                ))
            created_count += 1

    db.add(
        EntryStrategyUpload(
            tenant_id=current_user.tenant_id,
            user_id=current_user.user_id,
            filename=file.filename,
            symbols_json=json.dumps(list(parsed_strategies.keys())),
        )
    )

    db.commit()

    return EntryStrategyUploadResponse(
        symbols_processed=len(parsed_strategies),
        created_count=created_count,
        updated_count=updated_count,
        errors=row_errors,
        updated_at=now,
    )


@router.get("/template.csv")
def get_template():
    return {
        "symbol": "AMJLAND",
        "allocated": 30000,
        "quality": "Excellent",
        "exchange": "NSE",
        "entry1": 49,
        "entry2": 47,
        "entry3": 40,
        "da_enabled": "Y",
        "da_legs": 1,
        "da_e1_buyback": 3,
        "da_e2_buyback": 3,
        "da_e3_buyback": 5,
        "datrigger_offset": 1,
    }


def _get_cmp_for_symbol(symbol: str, db: Session, tenant_id: int | None, user_id: int | None) -> float | None:
    """Get current market price for a symbol from DB if available."""
    try:
        from db.models import EntryStrategy
        strategy = (
            db.query(EntryStrategy)
            .filter(
                EntryStrategy.tenant_id == tenant_id,
                EntryStrategy.user_id == user_id,
                EntryStrategy.symbol == symbol.upper(),
            )
            .first()
        )
        if not strategy:
            return None
        return None
    except Exception:
        return None


def _create_version(
    db: Session,
    strategy: EntryStrategy,
    action: str,
    levels: list[EntryLevel],
    changes_summary: str | None = None,
    tenant_id: int | None = None,
    user_id: int | None = None,
) -> EntryStrategyVersion:
    """Create a version snapshot of entry levels."""
    latest_version = (
        db.query(EntryStrategyVersion)
        .filter(EntryStrategyVersion.strategy_id == strategy.id)
        .order_by(EntryStrategyVersion.version_no.desc())
        .first()
    )
    version_no = (latest_version.version_no + 1) if latest_version else 1

    snapshot = json.dumps([
        {"level_no": l.level_no, "price": l.price, "is_active": l.is_active}
        for l in levels
    ])

    version = EntryStrategyVersion(
        tenant_id=tenant_id or strategy.tenant_id,
        user_id=user_id or strategy.user_id,
        strategy_id=strategy.id,
        version_no=version_no,
        action=action,
        levels_snapshot_json=snapshot,
        changes_summary=changes_summary,
    )
    db.add(version)
    return version


@router.get("/uploads", response_model=UploadHistoryResponse)
def get_upload_history(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    """Get upload history for the current user."""
    uploads = (
        db.query(EntryStrategyUpload)
        .filter(
            EntryStrategyUpload.tenant_id == current_user.tenant_id,
            EntryStrategyUpload.user_id == current_user.user_id,
        )
        .order_by(EntryStrategyUpload.created_at.desc())
        .limit(limit)
        .all()
    )

    return UploadHistoryResponse(
        uploads=[
            UploadHistoryItem(
                id=u.id,
                filename=u.filename,
                symbols=json.loads(u.symbols_json) if u.symbols_json else [],
                created_at=u.created_at,
            )
            for u in uploads
        ]
    )


@router.get("/{symbol}/versions", response_model=VersionListResponse)
def get_version_history(
    symbol: str,
    session_id: str = Query(..., description="Active session ID"),
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
    registry: SessionRegistry = Depends(get_session_registry),
):
    """Get version history for a specific strategy, scoped to the active session."""
    broker, broker_user_id = _get_broker_scope_from_session(session_id, registry, current_user)
    
    strategy = (
        db.query(EntryStrategy)
        .filter(
            EntryStrategy.tenant_id == current_user.tenant_id,
            EntryStrategy.user_id == current_user.user_id,
            EntryStrategy.broker == broker,
            EntryStrategy.broker_user_id == broker_user_id,
            EntryStrategy.symbol == symbol.upper(),
        )
        .first()
    )

    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    versions = (
        db.query(EntryStrategyVersion)
        .filter(EntryStrategyVersion.strategy_id == strategy.id)
        .order_by(EntryStrategyVersion.version_no.desc())
        .limit(limit)
        .all()
    )

    return VersionListResponse(
        versions=[
            VersionItem(
                id=v.id,
                version_no=v.version_no,
                action=v.action,
                levels=[
                    EntryLevelSchema(
                        level_no=l["level_no"],
                        price=l["price"],
                        is_active=l.get("is_active", True),
                    )
                    for l in json.loads(v.levels_snapshot_json)
                ],
                changes_summary=v.changes_summary,
                created_at=v.created_at,
            )
            for v in versions
        ]
    )


@router.post("/{symbol}/restore/{version_id}", response_model=RestoreVersionResponse)
def restore_version(
    symbol: str,
    version_id: int,
    session_id: str = Query(..., description="Active session ID"),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
    registry: SessionRegistry = Depends(get_session_registry),
):
    """Restore a strategy to a previous version, scoped to the active session."""
    broker, broker_user_id = _get_broker_scope_from_session(session_id, registry, current_user)
    
    strategy = (
        db.query(EntryStrategy)
        .filter(
            EntryStrategy.tenant_id == current_user.tenant_id,
            EntryStrategy.user_id == current_user.user_id,
            EntryStrategy.broker == broker,
            EntryStrategy.broker_user_id == broker_user_id,
            EntryStrategy.symbol == symbol.upper(),
        )
        .first()
    )

    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    version = (
        db.query(EntryStrategyVersion)
        .filter(
            EntryStrategyVersion.strategy_id == strategy.id,
            EntryStrategyVersion.id == version_id,
        )
        .first()
    )

    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    snapshot = json.loads(version.levels_snapshot_json)

    db.query(EntryLevel).filter(EntryLevel.strategy_id == strategy.id).delete()

    for level_data in snapshot:
        db.add(EntryLevel(
            strategy_id=strategy.id,
            level_no=level_data["level_no"],
            price=level_data["price"],
            is_active=level_data.get("is_active", True),
        ))

    now = datetime.utcnow()
    strategy.updated_at = now

    _create_version(
        db=db,
        strategy=strategy,
        action="restore",
        changes_summary=f"Restored to version {version.version_no}",
        levels=db.query(EntryLevel).filter(EntryLevel.strategy_id == strategy.id).all(),
    )

    db.commit()

    return RestoreVersionResponse(
        symbol=strategy.symbol,
        restored_to_version=version.version_no,
        updated_at=now,
    )


@router.post("/{symbol}/suggest-revision", response_model=SuggestRevisionResponse)
def suggest_revision(
    symbol: str,
    session_id: str = Query(..., description="Active session ID"),
    method: str = "align_to_cmp",
    pct_adjustment: float = 5.0,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
    registry: SessionRegistry = Depends(get_session_registry),
):
    """Suggest revised entry levels based on current market price or adjustment."""
    broker, broker_user_id = _get_broker_scope_from_session(session_id, registry, current_user)
    
    strategy = (
        db.query(EntryStrategy)
        .filter(
            EntryStrategy.tenant_id == current_user.tenant_id,
            EntryStrategy.user_id == current_user.user_id,
            EntryStrategy.broker == broker,
            EntryStrategy.broker_user_id == broker_user_id,
            EntryStrategy.symbol == symbol.upper(),
        )
        .first()
    )

    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    levels = (
        db.query(EntryLevel)
        .filter(EntryLevel.strategy_id == strategy.id)
        .order_by(EntryLevel.level_no)
        .all()
    )

    if not levels:
        raise HTTPException(status_code=400, detail="No levels found for this strategy")

    cmp_price: float | None = None
    try:
        from core.services.entry_strategy_service import get_entry_strategy_service
        service = get_entry_strategy_service()
        cmp_data = service.get_cmp_for_symbol(strategy.symbol, current_user.tenant_id, current_user.user_id)
        if cmp_data:
            cmp_price = cmp_data.get("last_price")
    except Exception:
        pass

    revised_levels: list[SuggestedRevision] = []

    if method == "align_to_cmp" and cmp_price:
        for level in levels:
            if level.level_no == 1:
                suggested = cmp_price
                rationale = f"CMP aligned to Level 1 (CMP: ₹{cmp_price:.2f})"
            else:
                gap_pct = (level.level_no - 1) * 5
                suggested = cmp_price * (1 - gap_pct / 100)
                rationale = f"Level {level.level_no} at {gap_pct}% below CMP"
            revised_levels.append(
                SuggestedRevision(
                    level_no=level.level_no,
                    original_price=level.price,
                    suggested_price=round(suggested, 2),
                    rationale=rationale,
                )
            )
    elif method == "volatility_band":
        for level in levels:
            suggested = level.price * (1 + (level.level_no - 1) * pct_adjustment / 100)
            rationale = f"Volatility adjustment: {pct_adjustment}% per level"
            revised_levels.append(
                SuggestedRevision(
                    level_no=level.level_no,
                    original_price=level.price,
                    suggested_price=round(suggested, 2),
                    rationale=rationale,
                )
            )
    elif method == "gap_fill":
        sorted_levels = sorted(levels, key=lambda x: x.price)
        base_price = sorted_levels[0].price if sorted_levels else 0
        for level in levels:
            gap = (level.price - base_price) / len(levels) if len(levels) > 1 else 0
            suggested = base_price + gap * level.level_no
            rationale = f"Even gap distribution from base ₹{base_price:.2f}"
            revised_levels.append(
                SuggestedRevision(
                    level_no=level.level_no,
                    original_price=level.price,
                    suggested_price=round(suggested, 2),
                    rationale=rationale,
                )
            )
    else:
        for level in levels:
            adjustment = pct_adjustment / 100
            suggested = level.price * (1 - adjustment)
            rationale = f"Fixed {pct_adjustment}% downward adjustment"
            revised_levels.append(
                SuggestedRevision(
                    level_no=level.level_no,
                    original_price=level.price,
                    suggested_price=round(suggested, 2),
                    rationale=rationale,
                )
            )

    return SuggestRevisionResponse(
        symbol=strategy.symbol,
        cmp_price=cmp_price,
        revised_levels=revised_levels,
    )


@router.patch("/{symbol}/apply-revision", response_model=ApplyRevisionResponse)
def apply_revision(
    symbol: str,
    payload: ApplyRevisionRequest,
    session_id: str = Query(..., description="Active session ID"),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
    registry: SessionRegistry = Depends(get_session_registry),
):
    """Apply selected level revisions to the database."""
    broker, broker_user_id = _get_broker_scope_from_session(session_id, registry, current_user)
    
    strategy = (
        db.query(EntryStrategy)
        .filter(
            EntryStrategy.tenant_id == current_user.tenant_id,
            EntryStrategy.user_id == current_user.user_id,
            EntryStrategy.broker == broker,
            EntryStrategy.broker_user_id == broker_user_id,
            EntryStrategy.symbol == symbol.upper(),
        )
        .first()
    )

    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    if not payload.levels:
        raise HTTPException(status_code=400, detail="No levels provided for update")

    updated_level_nos: list[int] = []
    now = datetime.utcnow()

    old_levels = db.query(EntryLevel).filter(EntryLevel.strategy_id == strategy.id).all()

    for item in payload.levels:
        if item.new_price <= 0:
            raise HTTPException(status_code=400, detail=f"Invalid price for level {item.level_no}: must be > 0")

        level = (
            db.query(EntryLevel)
            .filter(EntryLevel.strategy_id == strategy.id, EntryLevel.level_no == item.level_no)
            .first()
        )

        if not level:
            raise HTTPException(status_code=404, detail=f"Level {item.level_no} not found")

        level.price = item.new_price
        level.updated_at = now
        updated_level_nos.append(item.level_no)

    strategy.updated_at = now

    if old_levels:
        _create_version(
            db=db,
            strategy=strategy,
            action="revision",
            changes_summary=f"Updated {len(updated_level_nos)} levels: {updated_level_nos}",
            levels=old_levels,
        )

    db.commit()

    return ApplyRevisionResponse(
        symbol=strategy.symbol,
        updated_levels=updated_level_nos,
        updated_at=now,
    )


@router.post("/suggest-revision/bulk", response_model=BulkSuggestRevisionResponse)
def suggest_revision_bulk(
    payload: BulkSuggestRevisionRequest,
    session_id: str = Query(..., description="Active session ID"),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
    registry: SessionRegistry = Depends(get_session_registry),
):
    """Suggest revised entry levels for multiple symbols based on current market price or adjustment."""
    broker, broker_user_id = _get_broker_scope_from_session(session_id, registry, current_user)

    if not payload.symbols:
        raise HTTPException(status_code=400, detail="No symbols provided")

    if len(payload.symbols) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 symbols allowed per request")

    suggestions: list[BulkSuggestRevisionItem] = []
    symbols_upper = [s.upper() for s in payload.symbols]

    for symbol in symbols_upper:
        strategy = (
            db.query(EntryStrategy)
            .filter(
                EntryStrategy.tenant_id == current_user.tenant_id,
                EntryStrategy.user_id == current_user.user_id,
                EntryStrategy.broker == broker,
                EntryStrategy.broker_user_id == broker_user_id,
                EntryStrategy.symbol == symbol,
            )
            .first()
        )

        if not strategy:
            suggestions.append(BulkSuggestRevisionItem(
                symbol=symbol,
                cmp_price=None,
                revised_levels=[],
            ))
            continue

        levels = (
            db.query(EntryLevel)
            .filter(EntryLevel.strategy_id == strategy.id)
            .order_by(EntryLevel.level_no)
            .all()
        )

        if not levels:
            suggestions.append(BulkSuggestRevisionItem(
                symbol=symbol,
                cmp_price=None,
                revised_levels=[],
            ))
            continue

        cmp_price: float | None = None
        try:
            from core.services.entry_strategy_service import get_entry_strategy_service
            service = get_entry_strategy_service()
            cmp_data = service.get_cmp_for_symbol(strategy.symbol, current_user.tenant_id, current_user.user_id)
            if cmp_data:
                cmp_price = cmp_data.get("last_price")
        except Exception:
            pass

        revised_levels: list[SuggestedRevision] = []
        method = payload.method
        pct_adjustment = payload.pct_adjustment

        if method == "align_to_cmp" and cmp_price:
            for level in levels:
                if level.level_no == 1:
                    suggested = cmp_price
                    rationale = f"CMP aligned to Level 1 (CMP: ₹{cmp_price:.2f})"
                else:
                    gap_pct = (level.level_no - 1) * 5
                    suggested = cmp_price * (1 - gap_pct / 100)
                    rationale = f"Level {level.level_no} at {gap_pct}% below CMP"
                revised_levels.append(
                    SuggestedRevision(
                        level_no=level.level_no,
                        original_price=level.price,
                        suggested_price=round(suggested, 2),
                        rationale=rationale,
                    )
                )
        elif method == "volatility_band":
            for level in levels:
                suggested = level.price * (1 + (level.level_no - 1) * pct_adjustment / 100)
                rationale = f"Volatility adjustment: {pct_adjustment}% per level"
                revised_levels.append(
                    SuggestedRevision(
                        level_no=level.level_no,
                        original_price=level.price,
                        suggested_price=round(suggested, 2),
                        rationale=rationale,
                    )
                )
        elif method == "gap_fill":
            sorted_levels = sorted(levels, key=lambda x: x.price)
            base_price = sorted_levels[0].price if sorted_levels else 0
            for level in levels:
                gap = (level.price - base_price) / len(levels) if len(levels) > 1 else 0
                suggested = base_price + gap * level.level_no
                rationale = f"Even gap distribution from base ₹{base_price:.2f}"
                revised_levels.append(
                    SuggestedRevision(
                        level_no=level.level_no,
                        original_price=level.price,
                        suggested_price=round(suggested, 2),
                        rationale=rationale,
                    )
                )
        else:
            for level in levels:
                adjustment = pct_adjustment / 100
                suggested = level.price * (1 - adjustment)
                rationale = f"Fixed {pct_adjustment}% downward adjustment"
                revised_levels.append(
                    SuggestedRevision(
                        level_no=level.level_no,
                        original_price=level.price,
                        suggested_price=round(suggested, 2),
                        rationale=rationale,
                    )
                )

        suggestions.append(BulkSuggestRevisionItem(
            symbol=strategy.symbol,
            cmp_price=cmp_price,
            revised_levels=revised_levels,
        ))

    return BulkSuggestRevisionResponse(suggestions=suggestions)


@router.patch("/apply-revision/bulk", response_model=BulkApplyRevisionResponse)
def apply_revision_bulk(
    payload: BulkApplyRevisionRequest,
    session_id: str = Query(..., description="Active session ID"),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
    registry: SessionRegistry = Depends(get_session_registry),
):
    """Apply selected level revisions to multiple symbols in the database."""
    broker, broker_user_id = _get_broker_scope_from_session(session_id, registry, current_user)

    if not payload.updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    if len(payload.updates) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 symbols allowed per request")

    results: list[BulkApplyRevisionResult] = []
    total_updated = 0
    total_failed = 0

    for update in payload.updates:
        symbol = update.symbol.upper()

        strategy = (
            db.query(EntryStrategy)
            .filter(
                EntryStrategy.tenant_id == current_user.tenant_id,
                EntryStrategy.user_id == current_user.user_id,
                EntryStrategy.broker == broker,
                EntryStrategy.broker_user_id == broker_user_id,
                EntryStrategy.symbol == symbol,
            )
            .first()
        )

        if not strategy:
            results.append(BulkApplyRevisionResult(
                symbol=symbol,
                success=False,
                error="Strategy not found",
            ))
            total_failed += 1
            continue

        if not update.levels:
            results.append(BulkApplyRevisionResult(
                symbol=symbol,
                success=False,
                error="No levels provided",
            ))
            total_failed += 1
            continue

        updated_level_nos: list[int] = []
        now = datetime.utcnow()

        try:
            old_levels = db.query(EntryLevel).filter(EntryLevel.strategy_id == strategy.id).all()

            for item in update.levels:
                if item.new_price <= 0:
                    raise HTTPException(status_code=400, detail=f"Invalid price for level {item.level_no}: must be > 0")

                level = (
                    db.query(EntryLevel)
                    .filter(EntryLevel.strategy_id == strategy.id, EntryLevel.level_no == item.level_no)
                    .first()
                )

                if not level:
                    raise HTTPException(status_code=404, detail=f"Level {item.level_no} not found")

                level.price = item.new_price
                level.updated_at = now
                updated_level_nos.append(item.level_no)

            strategy.updated_at = now

            if old_levels:
                _create_version(
                    db=db,
                    strategy=strategy,
                    action="revision_bulk",
                    changes_summary=f"Bulk updated {len(updated_level_nos)} levels: {updated_level_nos}",
                    levels=old_levels,
                )

            db.commit()

            results.append(BulkApplyRevisionResult(
                symbol=strategy.symbol,
                success=True,
                updated_levels=updated_level_nos,
                updated_at=now,
            ))
            total_updated += 1

        except HTTPException:
            db.rollback()
            results.append(BulkApplyRevisionResult(
                symbol=symbol,
                success=False,
                error="Validation failed",
            ))
            total_failed += 1
        except Exception as e:
            db.rollback()
            results.append(BulkApplyRevisionResult(
                symbol=symbol,
                success=False,
                error=str(e),
            ))
            total_failed += 1

    return BulkApplyRevisionResponse(
        results=results,
        total_updated=total_updated,
        total_failed=total_failed,
    )
