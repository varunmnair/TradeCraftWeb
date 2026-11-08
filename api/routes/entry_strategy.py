from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.dependencies import get_current_user, get_db_session
from api.errors import ServiceError
from api.schemas.entry_strategy import (
    ApplyRevisionRequest,
    ApplyRevisionResponse,
    BulkApplyRevisionRequest,
    BulkApplyRevisionResponse,
    BulkApplyRevisionResult,
    BulkSuggestRevisionItem,
    BulkSuggestRevisionRequest,
    BulkSuggestRevisionResponse,
    DABulkEvalResponse,
    DAConfigSchema,
    DAEvalResultSchema,
    DAOverrideRequest,
    EntryLevelSchema,
    EntryStrategyFullSchema,
    EntryStrategyListResponse,
    EntryStrategySummarySchema,
    EntryStrategyUploadResponse,
    InlineUpdateRequest,
    InlineUpdateResponse,
    RestoreVersionResponse,
    SuggestedRevision,
    SuggestRevisionResponse,
    UploadHistoryItem,
    UploadHistoryResponse,
    VersionItem,
    VersionListResponse,
)
from core.auth.context import UserContext
from core.runtime.session_registry import SessionRegistry
from db.models import (
    EntryLevel,
    EntryStrategy,
    EntryStrategyUpload,
    EntryStrategyVersion,
)

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
    if (
        not current_user.is_dev
        and context.user_record_id
        and current_user.user_id != context.user_record_id
    ):
        raise HTTPException(status_code=403, detail="Session owned by another user")

    broker = context.broker_name
    broker_user_id = context.broker_user_id

    return broker, broker_user_id


def _trigger_ohlcv_for_entry_strategies(symbols: list[str], user_id: int | None):
    """Ensure OHLCV data is fresh for entry strategy symbols."""
    if not symbols:
        return

    from core.market_data.ohlcv_store import ensure_ohlcv

    symbols_stripped = [str(s).strip().upper() for s in symbols]
    ensure_ohlcv(symbols_stripped)
    logging.info(f"Ensured OHLCV data for {len(symbols_stripped)} entry strategy symbols")


def _require_active_connection_scope(
    current_user: UserContext,
    db: Session,
) -> tuple[int, str, str]:
    """Get broker_connection_id, broker, and broker_user_id from active connection.

    Returns tuple of (connection_id, broker, broker_user_id)

    Raises ServiceError with 409 if no active connection is set.
    """
    from api.dependencies import get_broker_connection_service

    if current_user.active_broker_connection_id is None:
        raise ServiceError(
            "No active broker connection. Connect/select a broker first.",
            error_code="no_active_connection",
            http_status=409,
        )

    connection_service = get_broker_connection_service()
    connection = connection_service.get_connection(
        current_user.active_broker_connection_id
    )

    if not connection:
        raise ServiceError(
            "Active broker connection not found. Please select a valid connection.",
            error_code="connection_not_found",
            http_status=409,
        )

    if connection.user_id != current_user.user_id:
        raise ServiceError(
            "Active broker connection belongs to another user.",
            error_code="forbidden",
            http_status=403,
        )

    return connection.id, connection.broker_name, connection.broker_user_id


@router.get("", response_model=EntryStrategyListResponse)
def list_entry_strategies(
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    """List entry strategies scoped to the active broker connection."""
    connection_id, broker, broker_user_id = _require_active_connection_scope(
        current_user, db
    )

    strategies = (
        db.query(EntryStrategy)
        .filter(
            EntryStrategy.user_id == current_user.user_id,
            EntryStrategy.broker == broker,
            EntryStrategy.broker_user_id == broker_user_id,
        )
        .all()
    )

    # Build holdings map from active session (if available)
    holdings_map = {}
    try:
        from api.dependencies import get_session_registry
        registry = get_session_registry()
        session = registry.find_session_for_user(current_user.user_id)
        if session:
            holdings = session.session_cache.get_holdings()
            for h in holdings:
                sym = h.get("tradingsymbol", "").replace("-BE", "").replace("#", "").upper()
                if sym:
                    holdings_map[sym] = h
    except Exception:
        pass

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

        # Map old THESIS_BREAK to REVIEW_REQUIRED — thesis break is now holdings-only
        review_status = s.review_status
        if review_status == "THESIS_BREAK":
            review_status = "REVIEW_REQUIRED"

        # Determine holdings status and entry level
        sym_clean = s.symbol.replace("-BE", "").replace("#", "").upper()
        holding = holdings_map.get(sym_clean)
        is_holding = holding is not None
        holding_entry_level = None
        if is_holding:
            # Determine which entry level the holding's average price is at
            avg_price = holding.get("average_price", 0) or 0
            if entry3 is not None and avg_price <= entry3:
                holding_entry_level = "E3"
            elif entry2 is not None and avg_price <= entry2:
                holding_entry_level = "E2"
            elif entry1 is not None and avg_price <= entry1:
                holding_entry_level = "E1"

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
                created_at=s.created_at,
                updated_at=s.updated_at,
                swing_eligible=s.swing_eligible,
                swing_avg_volume=s.swing_avg_volume,
                swing_atr_percent=s.swing_atr_percent,
                swing_range_percent=s.swing_range_percent,
                swing_reasons=json.loads(s.swing_reasons) if s.swing_reasons else None,
                thesis_break_price=s.thesis_break_price,
                review_status=review_status,
                last_evaluated_at=s.last_evaluated_at,
                last_entry_revision_at=s.last_entry_revision_at,
                da_eligible=s.da_eligible,
                da_status=s.da_status,
                da_confidence_score=s.da_confidence_score,
                da_last_evaluated_at=s.da_last_evaluated_at,
                is_holding=is_holding,
                holding_entry_level=holding_entry_level,
            )
        )

    return EntryStrategyListResponse(strategies=result)


@router.delete("/{symbol}")
def delete_entry_strategy(
    symbol: str,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    """Delete a single entry strategy by symbol, scoped to the active broker connection."""
    connection_id, broker, broker_user_id = _require_active_connection_scope(
        current_user, db
    )

    strategy = (
        db.query(EntryStrategy)
        .filter(
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


@router.patch("/{symbol}", response_model=InlineUpdateResponse)
def update_entry_strategy_inline(
    symbol: str,
    payload: InlineUpdateRequest,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    """Inline update of allocation and/or entry levels for a strategy."""
    connection_id, broker, broker_user_id = _require_active_connection_scope(
        current_user, db
    )

    strategy = (
        db.query(EntryStrategy)
        .filter(
            EntryStrategy.user_id == current_user.user_id,
            EntryStrategy.broker == broker,
            EntryStrategy.broker_user_id == broker_user_id,
            EntryStrategy.symbol == symbol.upper(),
        )
        .first()
    )

    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    now = datetime.utcnow()
    updated_fields: list[str] = []
    levels_changed = False

    # Update allocation if provided
    if payload.allocated is not None:
        strategy.allocated = payload.allocated
        updated_fields.append("allocated")

    # Collect current entry level prices for validation
    old_levels = (
        db.query(EntryLevel)
        .filter(EntryLevel.strategy_id == strategy.id)
        .all()
    )
    current_prices: dict[int, float] = {}
    for lvl in old_levels:
        if lvl.is_active:
            current_prices[lvl.level_no] = lvl.price

    # Build final entry prices
    e1 = payload.entry1 if payload.entry1 is not None else current_prices.get(1)
    e2 = payload.entry2 if payload.entry2 is not None else current_prices.get(2)
    e3 = payload.entry3 if payload.entry3 is not None else current_prices.get(3)

    # Auto-sort descending: Entry 1 (highest) > Entry 2 > Entry 3 (lowest)
    values = sorted([v for v in [e1, e2, e3] if v is not None], reverse=True)
    if len(values) >= 1 and e1 is not None:
        e1 = values[0]
    if len(values) >= 2 and e2 is not None:
        e2 = values[1]
    if len(values) >= 3 and e3 is not None:
        e3 = values[2]

    # Update entry levels
    for level_no, new_price in [
        (1, e1),
        (2, e2),
        (3, e3),
    ]:
        if new_price is None:
            continue
        if new_price <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"Entry {level_no} must be greater than 0",
            )

        level = next((lvl for lvl in old_levels if lvl.level_no == level_no), None)
        if level:
            if level.price != new_price:
                level.price = new_price
                level.updated_at = now
                updated_fields.append(f"entry{level_no}")
                levels_changed = True
        else:
            # Create level if it doesn't exist (shouldn't happen for normal flow)
            new_level = EntryLevel(
                strategy_id=strategy.id,
                level_no=level_no,
                price=new_price,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            db.add(new_level)
            updated_fields.append(f"entry{level_no}")
            levels_changed = True

    if not updated_fields:
        return InlineUpdateResponse(
            symbol=strategy.symbol,
            updated_fields=[],
            updated_at=now,
        )

    # Create version snapshot before entry level changes
    if levels_changed and old_levels:
        changes = [f for f in updated_fields if f.startswith("entry")]
        _create_version(
            db=db,
            strategy=strategy,
            action="inline_edit",
            changes_summary=f"Inline edit: {', '.join(changes)}",
            levels=old_levels,
        )

    strategy.updated_at = now
    if levels_changed:
        strategy.last_entry_revision_at = now

    db.commit()

    return InlineUpdateResponse(
        symbol=strategy.symbol,
        updated_fields=updated_fields,
        updated_at=now,
    )


@router.post("/bulk-delete")
def bulk_delete_entry_strategies(
    symbols: list[str],
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    """Delete multiple entry strategies by symbols, scoped to the active broker connection."""
    connection_id, broker, broker_user_id = _require_active_connection_scope(
        current_user, db
    )

    deleted_count = 0
    not_found = []

    for symbol in symbols:
        strategy = (
            db.query(EntryStrategy)
            .filter(
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


@router.get("/template.csv")
def get_template():
    return {
        "symbol": "BEL",
        "allocated": 30000,
        "entry1": 386.5,
        "entry2": 375,
        "entry3": 369,
    }


@router.get("/download.csv")
def download_strategies_csv(
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    """
    Download entry strategies as CSV for the active broker connection.
    Use this to save your strategies or re-upload after editing.
    """
    connection_id, broker, broker_user_id = _require_active_connection_scope(
        current_user, db
    )

    strategies = (
        db.query(EntryStrategy)
        .filter(
            EntryStrategy.user_id == current_user.user_id,
            EntryStrategy.broker == broker,
            EntryStrategy.broker_user_id == broker_user_id,
        )
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Symbol", "Allocated", "Entry1", "Entry2", "Entry3",
    ])

    for s in strategies:
        levels = (
            db.query(EntryLevel)
            .filter(EntryLevel.strategy_id == s.id)
            .order_by(EntryLevel.level_no)
            .all()
        )

        entry_prices = {l.level_no: l.price for l in levels}

        writer.writerow([
            s.symbol,
            s.allocated or "",
            entry_prices.get(1, ""),
            entry_prices.get(2, ""),
            entry_prices.get(3, ""),
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=entry_levels_{broker}_{broker_user_id}_{datetime.utcnow().strftime('%d%m')}.csv"
        },
    )


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


@router.get("/da/config", response_model=DAConfigSchema)
def get_da_config_endpoint():
    from core.da_config import get_da_config
    return get_da_config()


@router.get("/{symbol}", response_model=EntryStrategyFullSchema)
def get_entry_strategy(
    symbol: str,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    """Get a single entry strategy, scoped to the active broker connection."""
    connection_id, broker, broker_user_id = _require_active_connection_scope(
        current_user, db
    )

    strategy = (
        db.query(EntryStrategy)
        .filter(
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
        averaging_rules_summary=_compute_averaging_rules_summary(
            strategy.averaging_rules_json
        ),
        levels=[
            EntryLevelSchema(
                id=level.id,
                level_no=level.level_no,
                price=level.price,
                is_active=level.is_active,
            )
            for level in levels
        ],
        created_at=strategy.created_at,
        updated_at=strategy.updated_at,
        swing_eligible=strategy.swing_eligible,
        thesis_break_price=strategy.thesis_break_price,
        review_status=strategy.review_status,
        last_evaluated_at=strategy.last_evaluated_at,
        last_entry_revision_at=strategy.last_entry_revision_at,
        da_eligible=strategy.da_eligible,
        da_status=strategy.da_status,
        da_last_evaluated_at=strategy.da_last_evaluated_at,
        da_confidence_score=strategy.da_confidence_score,
        da_notes=strategy.da_notes,
        override_da_enabled=strategy.override_da_enabled,
        override_da_qty_pct=strategy.override_da_qty_pct,
        override_sell_offset=strategy.override_sell_offset,
        override_buyback_price=strategy.override_buyback_price,
        override_sell_price=strategy.override_sell_price,
    )


def _parse_entry_strategies_csv(
    text_content: str,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Parse the entry-strategy CSV into {symbol: strategy} dicts and row errors.

    Expected columns: Symbol, Allocated, Entry1, Entry2, Entry3. Header matching is
    case/space/underscore tolerant. Symbols are uppercased and any "NSE:"/"BSE:"
    prefix is stripped. Entry prices are auto-sorted descending (E1 > E2 > E3).
    """
    reader = csv.DictReader(io.StringIO(text_content))
    field_names = [fn.strip() for fn in reader.fieldnames or []]

    # Normalize header names so case/space/underscore variants all resolve
    # (e.g. "Entry1", "entry 1", "entry_1" -> "entry1")
    def _normalize_header(name: str) -> str:
        return name.strip().lower().replace(" ", "").replace("_", "")

    col_map: dict[str, str] = {}
    for fn in field_names:
        col_map.setdefault(_normalize_header(fn), fn)

    symbol_col = col_map.get("symbol")
    allocated_col = col_map.get("allocated")
    entry_cols = {i: col_map.get(f"entry{i}") for i in (1, 2, 3)}

    if not symbol_col or not entry_cols[1]:
        missing = []
        if not symbol_col:
            missing.append("Symbol")
        if not entry_cols[1]:
            missing.append("Entry1")
        raise HTTPException(
            status_code=400,
            detail=(
                "CSV must have Symbol, Allocated, Entry1, Entry2, Entry3 columns"
                + (f". Missing: {', '.join(missing)}" if missing else "")
            ),
        )

    parsed_strategies: dict[str, dict[str, Any]] = {}
    row_errors: list[dict[str, Any]] = []

    for row_num, row in enumerate(reader, start=2):
        try:
            row = {k.strip(): (v.strip() if v else "") for k, v in row.items()}

            # Symbol normalization: uppercase + strip "NSE:"/"BSE:" prefix
            symbol = row.get(symbol_col, "") or ""
            symbol = symbol.upper().strip()
            if symbol.startswith("NSE:") or symbol.startswith("BSE:"):
                symbol = symbol.split(":")[-1].strip()

            if not symbol:
                row_errors.append({"row": row_num, "error": "symbol is empty"})
                continue

            allocated = None
            allocated_val = row.get(allocated_col, "") if allocated_col else ""
            if allocated_val:
                try:
                    allocated = float(allocated_val)
                except ValueError:
                    row_errors.append(
                        {
                            "row": row_num,
                            "error": f"allocated '{allocated_val}' is not a valid number",
                        }
                    )
                    continue
                if allocated <= 0:
                    row_errors.append(
                        {"row": row_num, "error": "allocated must be greater than 0"}
                    )
                    continue

            row_invalid = False
            levels: dict[int, float] = {}
            for level_num, col in entry_cols.items():
                if not col:
                    continue
                price_str = row.get(col, "").strip()
                if not price_str:
                    continue
                try:
                    price = float(price_str)
                except ValueError:
                    row_errors.append(
                        {
                            "row": row_num,
                            "error": f"Entry {level_num} '{price_str}' is not a valid number",
                        }
                    )
                    row_invalid = True
                    break
                if price <= 0:
                    row_errors.append(
                        {
                            "row": row_num,
                            "error": f"Entry {level_num} must be greater than 0",
                        }
                    )
                    row_invalid = True
                    break
                levels[level_num] = price

            if row_invalid:
                continue

            if not levels:
                row_errors.append(
                    {"row": row_num, "error": f"no valid entry prices for {symbol}"}
                )
                continue

            # Auto-sort descending: Entry 1 (highest) > Entry 2 > Entry 3 (lowest)
            levels = {
                level_num + 1: price
                for level_num, price in enumerate(sorted(levels.values(), reverse=True))
            }

            parsed_strategies[symbol] = {
                "symbol": symbol,
                "allocated": allocated,
                "quality": None,
                "exchange": "NSE",
                "levels": levels,
            }

        except Exception as e:
            row_errors.append({"row": row_num, "error": str(e)})

    return parsed_strategies, row_errors


@router.post("/upload-csv", response_model=EntryStrategyUploadResponse)
async def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    """Upload CSV to create/update entry strategies, scoped to the active broker connection."""
    connection_id, broker, broker_user_id = _require_active_connection_scope(
        current_user, db
    )

    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    content = await file.read()
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid UTF-8 encoding")

    parsed_strategies, row_errors = _parse_entry_strategies_csv(text_content)

    if not parsed_strategies and not row_errors:
        raise HTTPException(status_code=400, detail="CSV file is empty")

    symbols_processed = set(parsed_strategies.keys())
    created_count = 0
    updated_count = 0
    deleted_count = 0
    now = datetime.utcnow()

    # Delete old strategies not in the uploaded CSV (non-premium only)
    if not current_user.is_premium:
        old_strategies = (
            db.query(EntryStrategy)
            .filter(
                EntryStrategy.user_id == current_user.user_id,
                EntryStrategy.broker == broker,
                EntryStrategy.broker_user_id == broker_user_id,
            )
            .all()
        )
        for old in old_strategies:
            if old.symbol not in symbols_processed:
                # Delete levels first
                db.query(EntryLevel).filter(EntryLevel.strategy_id == old.id).delete()
                db.delete(old)
                deleted_count += 1

    for symbol, strategy_data in parsed_strategies.items():
        levels_dict = strategy_data["levels"]

        existing = (
            db.query(EntryStrategy)
            .filter(
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
            existing.updated_at = now

            old_levels = (
                db.query(EntryLevel).filter(EntryLevel.strategy_id == existing.id).all()
            )
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
                db.add(
                    EntryLevel(
                        strategy_id=existing.id,
                        level_no=level_no,
                        price=price,
                        is_active=True,
                    )
                )
            updated_count += 1
        else:
            new_strategy = EntryStrategy(
                user_id=current_user.user_id,
                symbol=symbol,
                broker=broker,
                broker_user_id=broker_user_id,
                allocated=strategy_data.get("allocated"),
                quality=strategy_data.get("quality"),
                exchange=strategy_data.get("exchange", "NSE"),
                created_at=now,
                updated_at=now,
            )
            db.add(new_strategy)
            db.flush()

            for level_no, price in levels_dict.items():
                db.add(
                    EntryLevel(
                        strategy_id=new_strategy.id,
                        level_no=level_no,
                        price=price,
                        is_active=True,
                    )
                )
            created_count += 1

    db.add(
        EntryStrategyUpload(
            user_id=current_user.user_id,
            filename=file.filename,
            symbols_json=json.dumps(list(parsed_strategies.keys())),
        )
    )

    db.commit()

    _trigger_ohlcv_for_entry_strategies(list(parsed_strategies.keys()), current_user.user_id)

    return EntryStrategyUploadResponse(
        symbols_processed=len(parsed_strategies),
        created_count=created_count,
        updated_count=updated_count,
        deleted_count=deleted_count,
        errors=row_errors,
        updated_at=now,
    )


def _create_version(
    db: Session,
    strategy: EntryStrategy,
    action: str,
    levels: list[EntryLevel],
    changes_summary: str | None = None,
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

    snapshot = json.dumps(
        [
            {"level_no": level.level_no, "price": level.price, "is_active": level.is_active}
            for level in levels
        ]
    )

    version = EntryStrategyVersion(
        user_id=user_id or strategy.user_id,
        strategy_id=strategy.id,
        version_no=version_no,
        action=action,
        levels_snapshot_json=snapshot,
        changes_summary=changes_summary,
    )
    db.add(version)
    return version


@router.get("/{symbol}/versions", response_model=VersionListResponse)
def get_version_history(
    symbol: str,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    """Get version history for a specific strategy, scoped to the active broker connection."""
    connection_id, broker, broker_user_id = _require_active_connection_scope(
        current_user, db
    )

    strategy = (
        db.query(EntryStrategy)
        .filter(
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
                        level_no=level["level_no"],
                        price=level["price"],
                        is_active=level.get("is_active", True),
                    )
                    for level in json.loads(v.levels_snapshot_json)
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
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    """Restore a strategy to a previous version, scoped to the active broker connection."""
    connection_id, broker, broker_user_id = _require_active_connection_scope(
        current_user, db
    )

    strategy = (
        db.query(EntryStrategy)
        .filter(
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
        db.add(
            EntryLevel(
                strategy_id=strategy.id,
                level_no=level_data["level_no"],
                price=level_data["price"],
                is_active=level_data.get("is_active", True),
            )
        )

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
    style: str = "balanced",
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    """Suggest revised entry levels using market structure analysis with a given style."""
    connection_id, broker, broker_user_id = _require_active_connection_scope(
        current_user, db
    )

    strategy = (
        db.query(EntryStrategy)
        .filter(
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
        cmp_data = service.get_cmp_for_symbol(strategy.symbol, current_user.user_id)
        if cmp_data:
            cmp_price = cmp_data.get("last_price")
    except Exception:
        pass

    from core.services.market_structure_revision import (
        get_market_structure_revision_service,
    )
    from core.services.swing_eligibility import get_swing_eligibility_service

    revised_levels: list[SuggestedRevision] = []
    swing_eligible = None
    review_status = strategy.review_status
    thesis_break_price = strategy.thesis_break_price
    revision_reason = None

    revision_svc = get_market_structure_revision_service()
    revision = revision_svc.suggest_revision(
        strategy.symbol,
        [{"level_no": l.level_no, "price": l.price} for l in levels],
        [],
        cmp_price,
        style=style,
    )

    revision_reason = revision.get("revision_reason")
    thesis_break_price = revision.get("thesis_break_price")

    suggested_entries = {
        1: revision.get("suggested_entry1"),
        2: revision.get("suggested_entry2"),
        3: revision.get("suggested_entry3"),
    }

    for level in levels:
        suggested = suggested_entries.get(level.level_no)
        if suggested is not None:
            revised_levels.append(
                SuggestedRevision(
                    level_no=level.level_no,
                    original_price=level.price,
                    suggested_price=round(suggested, 2),
                    rationale=revision_reason or "Market structure based revision",
                )
            )

    if revised_levels:
        try:
            swing_svc = get_swing_eligibility_service()
            from core.market_data.ohlcv_store import get_ohlcv_multi

            symbol_clean = strategy.symbol.replace("-BE", "").replace("#", "").upper()
            ohlcv_data = get_ohlcv_multi([symbol_clean], days=60)
            candles = ohlcv_data.get(symbol_clean, [])
            if candles and len(candles) >= 20:
                swing_result = swing_svc.evaluate(strategy.symbol, candles)
                swing_eligible = swing_result["swing_eligible"]
        except Exception:
            pass

    return SuggestRevisionResponse(
        symbol=strategy.symbol,
        cmp_price=cmp_price,
        revised_levels=revised_levels,
        swing_eligible=swing_eligible,
        review_status=review_status,
        thesis_break_price=thesis_break_price,
        revision_reason=revision_reason,
        style=style,
    )


@router.patch("/{symbol}/apply-revision", response_model=ApplyRevisionResponse)
def apply_revision(
    symbol: str,
    payload: ApplyRevisionRequest,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    """Apply selected level revisions to the database."""
    connection_id, broker, broker_user_id = _require_active_connection_scope(
        current_user, db
    )

    strategy = (
        db.query(EntryStrategy)
        .filter(
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

    old_levels = (
        db.query(EntryLevel).filter(EntryLevel.strategy_id == strategy.id).all()
    )

    for item in payload.levels:
        if item.new_price <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid price for level {item.level_no}: must be > 0",
            )

        level = (
            db.query(EntryLevel)
            .filter(
                EntryLevel.strategy_id == strategy.id,
                EntryLevel.level_no == item.level_no,
            )
            .first()
        )

        if not level:
            raise HTTPException(
                status_code=404, detail=f"Level {item.level_no} not found"
            )

        level.price = item.new_price
        level.updated_at = now
        updated_level_nos.append(item.level_no)

    strategy.updated_at = now
    strategy.last_entry_revision_at = now
    strategy.review_status = "ACTIVE"
    if payload.thesis_break_price is not None:
        strategy.thesis_break_price = payload.thesis_break_price

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
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    """Suggest revised entry levels for multiple symbols using market structure analysis."""
    connection_id, broker, broker_user_id = _require_active_connection_scope(
        current_user, db
    )

    logging.info(
        f"suggest_revision_bulk: symbols={payload.symbols}, style={payload.style}"
    )

    if not payload.symbols:
        raise HTTPException(status_code=400, detail="No symbols provided")

    if len(payload.symbols) > 100:
        raise HTTPException(
            status_code=400, detail="Maximum 100 symbols allowed per request"
        )

    suggestions: list[BulkSuggestRevisionItem] = []
    symbols_upper = [s.upper() for s in payload.symbols]

    cmp_prices: dict[str, float | None] = {}

    try:
        from api.dependencies import get_global_cmp_manager
        cmp_manager = get_global_cmp_manager()
        cmp_prices = cmp_manager.get_cmp_for_symbols(symbols_upper, "NSE")
        logging.debug(f"CMP fetched via global manager: {cmp_prices}")
    except Exception as e:
        logging.warning(f"Could not fetch CMP from global manager: {e}")

    from core.services.market_structure_revision import (
        get_market_structure_revision_service,
    )
    from core.services.swing_eligibility import get_swing_eligibility_service

    revision_svc = get_market_structure_revision_service()

    for symbol in symbols_upper:
        strategy = (
            db.query(EntryStrategy)
            .filter(
                EntryStrategy.user_id == current_user.user_id,
                EntryStrategy.broker == broker,
                EntryStrategy.broker_user_id == broker_user_id,
                EntryStrategy.symbol == symbol,
            )
            .first()
        )

        if not strategy:
            suggestions.append(
                BulkSuggestRevisionItem(
                    symbol=symbol,
                    cmp_price=cmp_prices.get(symbol),
                    revised_levels=[],
                )
            )
            continue

        levels = (
            db.query(EntryLevel)
            .filter(EntryLevel.strategy_id == strategy.id)
            .filter(EntryLevel.is_active.is_(True))
            .order_by(EntryLevel.level_no)
            .all()
        )

        logging.debug(f"suggest_revision_bulk: symbol={symbol}, strategy_id={strategy.id}, levels_found={len(levels)}")

        if not levels:
            suggestions.append(
                BulkSuggestRevisionItem(
                    symbol=symbol,
                    cmp_price=cmp_prices.get(symbol),
                    revised_levels=[],
                )
            )
            continue

        cmp_price = cmp_prices.get(symbol)

        revised_levels: list[SuggestedRevision] = []
        swing_eligible = None
        thesis_break_price = strategy.thesis_break_price
        review_status = strategy.review_status
        revision_reason = None

        revision = revision_svc.suggest_revision(
            symbol,
            [{"level_no": l.level_no, "price": l.price} for l in levels],
            [],
            cmp_price,
            style=payload.style,
        )

        base_reason = revision.get("revision_reason") or "Market structure based revision"
        ema20 = revision.get("ema20")
        ema50 = revision.get("ema50")
        atr14 = revision.get("atr14")
        close_val = revision.get("current_close")
        zone = revision.get("trading_zone")
        support = revision.get("nearest_support")
        resistance = revision.get("nearest_resistance")
        gap_val = revision.get("gap")
        parts = [base_reason]
        if close_val is not None:
            parts.append(f"Close: {close_val:.2f}")
        if ema20 is not None:
            parts.append(f"EMA20: {ema20:.2f}")
        if ema50 is not None:
            parts.append(f"EMA50: {ema50:.2f}")
        if atr14 is not None:
            parts.append(f"ATR14: {atr14:.2f}")
        if zone:
            parts.append(f"Zone: {zone}")
        if support is not None:
            parts.append(f"Support: {support:.2f}")
        if resistance is not None:
            parts.append(f"Resistance: {resistance:.2f}")
        if gap_val is not None:
            parts.append(f"Gap: {gap_val:.2f}")
        revision_reason = " | ".join(parts)
        thesis_break_price = revision.get("thesis_break_price")

        for level in levels:
            suggested_map = {
                1: revision.get("suggested_entry1"),
                2: revision.get("suggested_entry2"),
                3: revision.get("suggested_entry3"),
            }
            suggested = suggested_map.get(level.level_no)
            if suggested is not None:
                revised_levels.append(
                    SuggestedRevision(
                        level_no=level.level_no,
                        original_price=level.price,
                        suggested_price=round(suggested, 2),
                        rationale=revision_reason,
                    )
                )

        try:
            swing_svc = get_swing_eligibility_service()
            from core.market_data.ohlcv_store import get_ohlcv_multi

            symbol_clean = symbol.replace("-BE", "").replace("#", "").upper()
            ohlcv_data = get_ohlcv_multi([symbol_clean], days=60)
            candles = ohlcv_data.get(symbol_clean, [])
            if candles and len(candles) >= 20:
                swing_result = swing_svc.evaluate(symbol, candles)
                swing_eligible = swing_result["swing_eligible"]
        except Exception:
            pass

        suggestions.append(
            BulkSuggestRevisionItem(
                symbol=strategy.symbol,
                cmp_price=cmp_price,
                revised_levels=revised_levels,
                swing_eligible=swing_eligible,
                review_status=review_status,
                thesis_break_price=thesis_break_price,
                revision_reason=revision_reason,
                style=payload.style,
            )
        )

    return BulkSuggestRevisionResponse(suggestions=suggestions)


@router.patch("/apply-revision/bulk", response_model=BulkApplyRevisionResponse)
def apply_revision_bulk(
    payload: BulkApplyRevisionRequest,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    """Apply selected level revisions to multiple symbols in the database."""
    connection_id, broker, broker_user_id = _require_active_connection_scope(
        current_user, db
    )

    if not payload.updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    if len(payload.updates) > 100:
        raise HTTPException(
            status_code=400, detail="Maximum 100 symbols allowed per request"
        )

    results: list[BulkApplyRevisionResult] = []
    total_updated = 0
    total_failed = 0

    for update in payload.updates:
        symbol = update.symbol.upper()

        strategy = (
            db.query(EntryStrategy)
            .filter(
                EntryStrategy.user_id == current_user.user_id,
                EntryStrategy.broker == broker,
                EntryStrategy.broker_user_id == broker_user_id,
                EntryStrategy.symbol == symbol,
            )
            .first()
        )

        if not strategy:
            results.append(
                BulkApplyRevisionResult(
                    symbol=symbol,
                    success=False,
                    error="Strategy not found",
                )
            )
            total_failed += 1
            continue

        if not update.levels:
            results.append(
                BulkApplyRevisionResult(
                    symbol=symbol,
                    success=False,
                    error="No levels provided",
                )
            )
            total_failed += 1
            continue

        updated_level_nos: list[int] = []
        now = datetime.utcnow()

        try:
            old_levels = (
                db.query(EntryLevel).filter(EntryLevel.strategy_id == strategy.id).all()
            )

            for item in update.levels:
                if item.new_price <= 0:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid price for level {item.level_no}: must be > 0",
                    )

                level = (
                    db.query(EntryLevel)
                    .filter(
                        EntryLevel.strategy_id == strategy.id,
                        EntryLevel.level_no == item.level_no,
                    )
                    .first()
                )

                if not level:
                    raise HTTPException(
                        status_code=404, detail=f"Level {item.level_no} not found"
                    )

                level.price = item.new_price
                level.updated_at = now
                updated_level_nos.append(item.level_no)

            strategy.updated_at = now
            strategy.last_entry_revision_at = now
            strategy.review_status = "ACTIVE"
            if update.thesis_break_price is not None:
                strategy.thesis_break_price = update.thesis_break_price

            if old_levels:
                _create_version(
                    db=db,
                    strategy=strategy,
                    action="revision_bulk",
                    changes_summary=f"Bulk updated {len(updated_level_nos)} levels: {updated_level_nos}",
                    levels=old_levels,
                )

            db.commit()

            results.append(
                BulkApplyRevisionResult(
                    symbol=strategy.symbol,
                    success=True,
                    updated_levels=updated_level_nos,
                    updated_at=now,
                )
            )
            total_updated += 1

        except HTTPException:
            db.rollback()
            results.append(
                BulkApplyRevisionResult(
                    symbol=symbol,
                    success=False,
                    error="Validation failed",
                )
            )
            total_failed += 1
        except Exception as e:
            db.rollback()
            results.append(
                BulkApplyRevisionResult(
                    symbol=symbol,
                    success=False,
                    error=str(e),
                )
            )
            total_failed += 1

    return BulkApplyRevisionResponse(
        results=results,
        total_updated=total_updated,
        total_failed=total_failed,
    )


class EvaluateStrategyResponse(BaseModel):
    symbol: str
    review_status: str
    swing_eligible: bool | None = None
    swing_avg_volume: float | None = None
    swing_atr_percent: float | None = None
    swing_range_percent: float | None = None
    swing_reasons: list[str] | None = None
    thesis_break_price: float | None = None
    last_evaluated_at: datetime | None = None
    reason: str | None = None


@router.post("/{symbol}/evaluate", response_model=EvaluateStrategyResponse)
def evaluate_strategy(
    symbol: str,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    """Evaluate a single entry strategy for review eligibility and thesis breach."""
    connection_id, broker, broker_user_id = _require_active_connection_scope(
        current_user, db
    )

    strategy = (
        db.query(EntryStrategy)
        .filter(
            EntryStrategy.user_id == current_user.user_id,
            EntryStrategy.broker == broker,
            EntryStrategy.broker_user_id == broker_user_id,
            EntryStrategy.symbol == symbol.upper(),
        )
        .first()
    )

    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    from core.market_data.ohlcv_store import ensure_ohlcv, get_ohlcv_multi
    from core.services.swing_eligibility import get_swing_eligibility_service
    from core.strategy_config import get_strategy_config

    config = get_strategy_config()
    symbol_clean = symbol.replace("-BE", "").replace("#", "").upper()
    ensure_ohlcv([symbol_clean], days=90)
    ohlcv_data = get_ohlcv_multi([symbol_clean], days=90)
    candles = ohlcv_data.get(symbol_clean, [])

    now = datetime.utcnow()
    review_status = "ACTIVE"
    reason = None
    swing_eligible = strategy.swing_eligible
    swing_avg_volume: float | None = None
    swing_atr_percent: float | None = None
    swing_range_percent: float | None = None
    swing_reasons: list[str] | None = None

    if candles and len(candles) >= 20:
        swing_svc = get_swing_eligibility_service()
        swing_result = swing_svc.evaluate(symbol, candles)
        swing_eligible = swing_result["swing_eligible"]
        swing_avg_volume = swing_result.get("avg_volume_20")
        swing_atr_percent = swing_result.get("atr_percent")
        swing_range_percent = swing_result.get("range_percent")
        swing_reasons = swing_result.get("reasons") or []

        updated_at = strategy.updated_at
        if updated_at and updated_at.tzinfo is not None:
            updated_at = updated_at.replace(tzinfo=None)
        if updated_at:
            days_since_update = (now - updated_at).days
            review_days = config.strategy_review_days
            if days_since_update >= review_days:
                review_status = "REVIEW_REQUIRED"
                reason = f"Last update {days_since_update}d ago (review every {review_days}d)"
            else:
                review_status = "ACTIVE"
                reason = f"Last update {days_since_update}d ago, next review in {review_days - days_since_update}d"
        else:
            review_status = "REVIEW_REQUIRED"
            reason = "No update history — initial review needed"
    else:
        reason = "Insufficient OHLCV data for evaluation"

    strategy.swing_eligible = swing_eligible
    strategy.swing_avg_volume = swing_avg_volume
    strategy.swing_atr_percent = swing_atr_percent
    strategy.swing_range_percent = swing_range_percent
    strategy.swing_reasons = json.dumps(swing_reasons) if swing_reasons else None
    strategy.review_status = review_status
    strategy.last_evaluated_at = now
    db.commit()

    return EvaluateStrategyResponse(
        symbol=strategy.symbol,
        review_status=review_status,
        swing_eligible=swing_eligible,
        swing_avg_volume=swing_avg_volume,
        swing_atr_percent=swing_atr_percent,
        swing_range_percent=swing_range_percent,
        swing_reasons=swing_reasons,
        thesis_break_price=strategy.thesis_break_price,
        last_evaluated_at=now,
        reason=reason,
    )


@router.post("/evaluate-all", response_model=list[EvaluateStrategyResponse])
def evaluate_all_strategies(
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    """Evaluate all entry strategies for the current user."""
    connection_id, broker, broker_user_id = _require_active_connection_scope(
        current_user, db
    )

    strategies = (
        db.query(EntryStrategy)
        .filter(
            EntryStrategy.user_id == current_user.user_id,
            EntryStrategy.broker == broker,
            EntryStrategy.broker_user_id == broker_user_id,
        )
        .all()
    )

    from core.market_data.ohlcv_store import ensure_ohlcv, get_ohlcv_multi
    from core.services.swing_eligibility import get_swing_eligibility_service
    from core.strategy_config import get_strategy_config

    config = get_strategy_config()
    symbols_clean = [
        s.symbol.replace("-BE", "").replace("#", "").upper()
        for s in strategies
    ]
    ensure_ohlcv(symbols_clean, days=90)
    ohlcv_data = get_ohlcv_multi(symbols_clean, days=90)

    swing_svc = get_swing_eligibility_service()
    now = datetime.utcnow()
    results: list[EvaluateStrategyResponse] = []

    for strategy in strategies:
        symbol_clean = strategy.symbol.replace("-BE", "").replace("#", "").upper()
        candles = ohlcv_data.get(symbol_clean, [])
        review_status = "ACTIVE"
        reason = None
        swing_eligible = strategy.swing_eligible
        swing_avg_volume: float | None = None
        swing_atr_percent: float | None = None
        swing_range_percent: float | None = None
        swing_reasons: list[str] | None = None

        if candles and len(candles) >= 20:
            swing_result = swing_svc.evaluate(strategy.symbol, candles)
            swing_eligible = swing_result["swing_eligible"]
            swing_avg_volume = swing_result.get("avg_volume_20")
            swing_atr_percent = swing_result.get("atr_percent")
            swing_range_percent = swing_result.get("range_percent")
            swing_reasons = swing_result.get("reasons") or []

            review_days = config.strategy_review_days
            updated_at = strategy.updated_at
            if updated_at and updated_at.tzinfo is not None:
                updated_at = updated_at.replace(tzinfo=None)
            days_since_update = (now - updated_at).days if updated_at else 999
            if days_since_update >= review_days:
                review_status = "REVIEW_REQUIRED"
                reason = f"Last update {days_since_update}d ago (review every {review_days}d)"
            else:
                review_status = "ACTIVE"
                reason = f"Last update {days_since_update}d ago, next review in {review_days - days_since_update}d"
        else:
            reason = "Insufficient OHLCV data for evaluation"

        strategy.swing_eligible = swing_eligible
        strategy.swing_avg_volume = swing_avg_volume
        strategy.swing_atr_percent = swing_atr_percent
        strategy.swing_range_percent = swing_range_percent
        strategy.swing_reasons = json.dumps(swing_reasons) if swing_reasons else None
        strategy.review_status = review_status
        strategy.last_evaluated_at = now
        results.append(
            EvaluateStrategyResponse(
                symbol=strategy.symbol,
                review_status=review_status,
                swing_eligible=swing_eligible,
                swing_avg_volume=swing_avg_volume,
                swing_atr_percent=swing_atr_percent,
                swing_range_percent=swing_range_percent,
                swing_reasons=swing_reasons,
                thesis_break_price=strategy.thesis_break_price,
                last_evaluated_at=now,
                reason=reason,
            )
        )

    db.commit()
    return results


@router.post("/{symbol}/da/evaluate", response_model=DAEvalResultSchema)
def evaluate_da(
    symbol: str,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    connection_id, broker, broker_user_id = _require_active_connection_scope(
        current_user, db
    )
    strategy = (
        db.query(EntryStrategy)
        .filter(
            EntryStrategy.user_id == current_user.user_id,
            EntryStrategy.broker == broker,
            EntryStrategy.broker_user_id == broker_user_id,
            EntryStrategy.symbol == symbol.upper(),
        )
        .first()
    )
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    from core.market_data.ohlcv_store import ensure_ohlcv, get_ohlcv_multi
    from core.services.da_evaluation import get_da_evaluation_service

    symbol_clean = symbol.replace("-BE", "").replace("#", "").upper()
    ensure_ohlcv([symbol_clean], days=90)
    ohlcv_data = get_ohlcv_multi([symbol_clean], days=90)
    candles = ohlcv_data.get(symbol_clean, [])

    from core.services.entry_strategy_service import _strategy_to_entry_dict

    strategy_dict = _strategy_to_entry_dict(strategy)
    svc = get_da_evaluation_service()
    result = svc.evaluate(
        symbol=symbol,
        holding=None,
        entry_strategy=strategy_dict,
        candles=candles,
    )

    strategy.da_eligible = result["da_eligible"]
    strategy.da_status = result["da_status"]
    strategy.da_last_evaluated_at = result["da_last_evaluated_at"]
    strategy.da_confidence_score = result["da_confidence_score"]
    strategy.da_notes = result["da_notes"]
    db.commit()

    return _prune_da_result(result)


@router.post("/da/evaluate-all", response_model=DABulkEvalResponse)
def evaluate_all_da(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    session_id = payload.get("session_id", "")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    connection_id, broker, broker_user_id = _require_active_connection_scope(
        current_user, db
    )

    from api.dependencies import get_session_registry
    registry = get_session_registry()
    registry.require_access(session_id, current_user)
    context = registry.get_session(session_id)
    if not context:
        raise HTTPException(status_code=404, detail="Session not found")

    from core.session_data import SessionDataManager
    dm = SessionDataManager(context)
    dm.load_or_refresh_holdings()
    holdings = [h for h in (context.session_cache.holdings or []) if h.get("symbol", "").strip()]
    strategies = (
        db.query(EntryStrategy)
        .filter(
            EntryStrategy.user_id == current_user.user_id,
            EntryStrategy.broker == broker,
            EntryStrategy.broker_user_id == broker_user_id,
        )
        .all()
    )
    strategy_dicts: dict[str, dict] = {}
    symbols = []
    for s in strategies:
        d = {
            "symbol": s.symbol,
            "dynamic_averaging_enabled": s.dynamic_averaging_enabled,
            "thesis_break_price": s.thesis_break_price,
            "override_da_enabled": s.override_da_enabled,
            "override_da_qty_pct": s.override_da_qty_pct,
            "override_sell_offset": s.override_sell_offset,
            "override_buyback_price": s.override_buyback_price,
            "override_sell_price": s.override_sell_price,
        }
        strategy_dicts[s.symbol] = d
        symbols.append(s.symbol)

    symbols_clean = [s.replace("-BE", "").replace("#", "").upper() for s in symbols]
    from core.market_data.ohlcv_store import ensure_ohlcv, get_ohlcv_multi
    ensure_ohlcv(symbols_clean, days=90)
    ohlcv_data = get_ohlcv_multi(symbols_clean, days=90)

    from core.services.da_evaluation import get_da_evaluation_service
    svc = get_da_evaluation_service()
    results = svc.evaluate_all(holdings, strategy_dicts, ohlcv_data)

    for r in results:
        symbol = r["symbol"]
        s = next((x for x in strategies if x.symbol == symbol), None)
        if s:
            s.da_eligible = r["da_eligible"]
            s.da_status = r["da_status"]
            s.da_last_evaluated_at = r["da_last_evaluated_at"]
            s.da_confidence_score = r["da_confidence_score"]
            s.da_notes = r["da_notes"]
    db.commit()

    return DABulkEvalResponse(
        session_id=session_id,
        results=[_prune_da_result(r) for r in results],
    )


@router.put("/{symbol}/da/overrides", response_model=dict)
def update_da_overrides(
    symbol: str,
    payload: DAOverrideRequest,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    connection_id, broker, broker_user_id = _require_active_connection_scope(
        current_user, db
    )
    strategy = (
        db.query(EntryStrategy)
        .filter(
            EntryStrategy.user_id == current_user.user_id,
            EntryStrategy.broker == broker,
            EntryStrategy.broker_user_id == broker_user_id,
            EntryStrategy.symbol == symbol.upper(),
        )
        .first()
    )
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    if payload.override_da_enabled is not None:
        strategy.override_da_enabled = payload.override_da_enabled
    if payload.override_da_qty_pct is not None:
        strategy.override_da_qty_pct = payload.override_da_qty_pct
    if payload.override_sell_offset is not None:
        strategy.override_sell_offset = payload.override_sell_offset
    if payload.override_buyback_price is not None:
        strategy.override_buyback_price = payload.override_buyback_price
    if payload.override_sell_price is not None:
        strategy.override_sell_price = payload.override_sell_price

    strategy.updated_at = datetime.utcnow()
    db.commit()

    return {"symbol": symbol, "success": True}


@router.put("/da/config", response_model=DAConfigSchema)
def update_da_config_endpoint(payload: DAConfigSchema):
    from core.da_config import update_da_config
    return update_da_config(payload.model_dump(exclude_unset=True))


def _prune_da_result(r: dict) -> dict:
    keys = [
        "symbol", "da_eligible", "da_status", "da_confidence_score",
        "da_confidence_label", "da_last_evaluated_at", "da_notes",
        "recommended_sell_trigger", "recommended_sell_limit",
        "recommended_buyback_price", "recommended_da_qty", "recommended_da_qty_pct",
        "expected_sell_value", "expected_buyback_value", "expected_charges",
        "expected_net_profit", "position_risk_score",
        "range_high", "range_low", "range_width", "range_pct",
    ]
    return {k: r.get(k) for k in keys}
