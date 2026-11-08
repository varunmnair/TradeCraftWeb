from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from api.dependencies import get_current_user, get_session_registry
from core.auth.context import UserContext
from core.runtime.session_registry import SessionRegistry
from core.session_data import SessionDataManager

logger = logging.getLogger("tradecraftx.holdings")


router = APIRouter(prefix="/holdings", tags=["holdings"])


class OrderHistoryStatusResponse(BaseModel):
    available: bool
    trade_count: int
    symbol_count: int
    fetched_at: Optional[str]
    source: Optional[str]
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    skipped_symbols: List[str] = []
    errors: List[str] = []


class HoldingsResponse(BaseModel):
    session_id: str
    broker: str
    broker_user_id: str
    holdings: List[Dict[str, Any]]
    order_history: OrderHistoryStatusResponse


class FetchOrderHistoryRequest(BaseModel):
    days: int = 100


@router.get("/{session_id}", response_model=HoldingsResponse)
def get_holdings(
    session_id: str,
    current_user: UserContext = Depends(get_current_user),
    registry: SessionRegistry = Depends(get_session_registry),
):
    """
    Get holdings for the current session.
    Loads from DB if available, otherwise fetches from broker.
    Order history fields are populated if order history has been fetched.
    """
    registry.require_access(session_id, current_user)
    context = registry.get_session(session_id)
    if not context:
        raise HTTPException(status_code=404, detail="Session not found")

    dm = SessionDataManager(context)

    # Load from DB or fetch from broker
    holdings = dm.load_or_refresh_holdings()

    # Enrich with order history data from session cache
    enriched = context.session_cache.get_holdings_enriched()

    # Get order history status
    oh_status = context.session_cache.get_order_history_status()

    return HoldingsResponse(
        session_id=session_id,
        broker=context.broker_name,
        broker_user_id=context.broker_user_id or "",
        holdings=enriched,
        order_history=OrderHistoryStatusResponse(
            available=oh_status["available"],
            trade_count=oh_status["trade_count"],
            symbol_count=oh_status["symbol_count"],
            fetched_at=oh_status["fetched_at"].isoformat() if oh_status["fetched_at"] else None,
            source=oh_status["source"],
        ),
    )


@router.get("/{session_id}/analyze")
def analyze_holdings(
    session_id: str,
    current_user: UserContext = Depends(get_current_user),
    registry: SessionRegistry = Depends(get_session_registry),
):
    """
    Analyze holdings with calculated metrics.
    """
    from core.holdings import HoldingsAnalyzer

    context = registry.require_access(session_id, current_user)
    if not context:
        raise HTTPException(
            status_code=401,
            detail="Session expired. Please restart your session from the Sessions page.",
        )

    context.session_cache.refresh_all_caches()
    holdings_analyzer = HoldingsAnalyzer(
        context.broker_user_id,
        context.broker_name,
        context.user_record_id,
    )
    results = holdings_analyzer.analyze_holdings(
        context.broker, context.session_cache.get_cmp_manager()
    )

    return {"results": results}


@router.post("/{session_id}/holdings/refresh", response_model=HoldingsResponse)
def refresh_holdings(
    session_id: str,
    current_user: UserContext = Depends(get_current_user),
    registry: SessionRegistry = Depends(get_session_registry),
):
    """
    Refresh holdings by fetching from broker and storing in DB.
    Use this when you want fresh data from the broker.
    """
    registry.require_access(session_id, current_user)
    context = registry.get_session(session_id)
    if not context:
        raise HTTPException(status_code=404, detail="Session not found")

    dm = SessionDataManager(context)

    # Fetch fresh from broker and store
    dm.refresh_holdings()

    # Enrich with order history data
    enriched = context.session_cache.get_holdings_enriched()

    oh_status = context.session_cache.get_order_history_status()

    return HoldingsResponse(
        session_id=session_id,
        broker=context.broker_name,
        broker_user_id=context.broker_user_id or "",
        holdings=enriched,
        order_history=OrderHistoryStatusResponse(
            available=oh_status["available"],
            trade_count=oh_status["trade_count"],
            symbol_count=oh_status["symbol_count"],
            fetched_at=oh_status["fetched_at"].isoformat() if oh_status["fetched_at"] else None,
            source=oh_status["source"],
            date_from=oh_status.get("date_from"),
            date_to=oh_status.get("date_to"),
        ),
    )


@router.get("/{session_id}/order-history", response_model=OrderHistoryStatusResponse)
def get_order_history_status(
    session_id: str,
    current_user: UserContext = Depends(get_current_user),
    registry: SessionRegistry = Depends(get_session_registry),
):
    """Get the status of order history for this session."""
    registry.require_access(session_id, current_user)
    context = registry.get_session(session_id)
    if not context:
        raise HTTPException(status_code=404, detail="Session not found")

    oh_status = context.session_cache.get_order_history_status()

    return OrderHistoryStatusResponse(
        available=oh_status["available"],
        trade_count=oh_status["trade_count"],
        symbol_count=oh_status["symbol_count"],
        fetched_at=oh_status["fetched_at"].isoformat() if oh_status["fetched_at"] else None,
        source=oh_status["source"],
        date_from=oh_status.get("date_from"),
        date_to=oh_status.get("date_to"),
    )


class TradeResponse(BaseModel):
    symbol: str
    trade_date: Optional[str]
    side: str
    quantity: int
    price: float
    trade_id: Optional[str]
    source: str


class TradesListResponse(BaseModel):
    trades: List[Dict[str, Any]]
    total_count: int
    symbol: Optional[str] = None


@router.get("/{session_id}/trades", response_model=TradesListResponse)
def get_trades(
    session_id: str,
    symbol: Optional[str] = None,
    current_user: UserContext = Depends(get_current_user),
    registry: SessionRegistry = Depends(get_session_registry),
):
    """
    Get trades for this session, optionally filtered by symbol.
    Returns trades ordered by date (oldest first).
    """
    registry.require_access(session_id, current_user)
    context = registry.get_session(session_id)
    if not context:
        raise HTTPException(status_code=404, detail="Session not found")

    from db.database import SessionLocal
    from db.models import UserTrade

    db = SessionLocal()
    try:
        query = db.query(UserTrade).filter(UserTrade.session_id == session_id)

        if symbol:
            symbol_clean = symbol.strip().upper()
            query = query.filter(UserTrade.symbol == symbol_clean)

        trades = query.order_by(UserTrade.trade_date.asc()).all()

        trades_data = [
            {
                "symbol": t.symbol,
                "trade_date": t.trade_date,
                "side": t.side,
                "quantity": t.quantity,
                "price": t.price,
                "trade_id": t.trade_id,
                "source": t.source,
            }
            for t in trades
        ]

        return TradesListResponse(
            trades=trades_data,
            total_count=len(trades_data),
            symbol=symbol,
        )
    finally:
        db.close()


@router.post("/{session_id}/order-history/fetch", response_model=OrderHistoryStatusResponse)
def fetch_order_history(
    session_id: str,
    payload: FetchOrderHistoryRequest,
    current_user: UserContext = Depends(get_current_user),
    registry: SessionRegistry = Depends(get_session_registry),
):
    """
    Fetch order history from Upstox broker for the configured number of days.
    This replaces any existing order history for the session.
    """
    registry.require_access(session_id, current_user)
    context = registry.get_session(session_id)
    if not context:
        raise HTTPException(status_code=404, detail="Session not found")

    if context.broker_name != "upstox":
        raise HTTPException(
            status_code=400,
            detail="Order history fetch is only supported for Upstox broker. Use upload endpoint for Zerodha.",
        )

    try:
        # Get orders from Upstox broker
        orders = context.broker.trades(days=payload.days) or []
        logging.info(f"Fetched {len(orders)} orders from Upstox broker (requested {payload.days} days)")

        # Convert orders to trade format
        trades = []
        for order in orders:
            # Parse fill_timestamp to get trade_date
            fill_ts = order.get("fill_timestamp")
            if isinstance(fill_ts, datetime):
                trade_date = fill_ts.strftime("%Y-%m-%d")
            elif isinstance(fill_ts, str):
                try:
                    trade_date = datetime.strptime(fill_ts[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
                except ValueError:
                    trade_date = None
            else:
                trade_date = None

            trades.append({
                "symbol": order.get("tradingsymbol", "").replace("-EQ", "").strip().upper(),
                "isin": order.get("isin"),
                "trade_date": trade_date,
                "exchange": order.get("exchange", "NSE"),
                "segment": "EQ",
                "series": "EQ",
                "side": "BUY" if order.get("transaction_type") == "BUY" else "SELL",
                "quantity": order.get("quantity", 0),
                "price": order.get("average_price", 0),
                "trade_id": order.get("trade_id"),
                "order_id": order.get("order_id"),
                "order_execution_time": trade_date,
                "source": "upstox_api",
            })

        # Store in session cache
        context.session_cache.set_order_history(trades, source="upstox_api")

        # Also store in database for persistence across page refreshes
        _store_trades_in_db(
            user_id=current_user.user_id,
            session_id=session_id,
            broker=context.broker_name,
            trades=trades,
        )

        oh_status = context.session_cache.get_order_history_status()

        return OrderHistoryStatusResponse(
            available=oh_status["available"],
            trade_count=oh_status["trade_count"],
            symbol_count=oh_status["symbol_count"],
            fetched_at=oh_status["fetched_at"].isoformat() if oh_status["fetched_at"] else None,
            source=oh_status["source"],
            date_from=oh_status.get("date_from"),
            date_to=oh_status.get("date_to"),
        )

    except Exception as e:
        logging.error(f"Error fetching order history: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch order history: {str(e)}")


@router.post("/{session_id}/order-history/upload", response_model=OrderHistoryStatusResponse)
async def upload_order_history(
    session_id: str,
    file: UploadFile = File(...),
    current_user: UserContext = Depends(get_current_user),
    registry: SessionRegistry = Depends(get_session_registry),
):
    """
    Upload Zerodha tradebook CSV.
    This replaces any existing order history for the session.
    
    Expected CSV format:
    symbol,isin,trade_date,exchange,segment,series,trade_type,auction,quantity,price,trade_id,order_id,order_execution_time
    """
    registry.require_access(session_id, current_user)
    context = registry.get_session(session_id)
    if not context:
        raise HTTPException(status_code=404, detail="Session not found")

    if context.broker_name != "zerodha":
        raise HTTPException(
            status_code=400,
            detail="Tradebook upload is only supported for Zerodha broker.",
        )

    # Read and parse CSV
    content = await file.read()
    try:
        decoded_content = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            decoded_content = content.decode("latin-1")
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid file encoding")

    trades = []
    reader = csv.DictReader(io.StringIO(decoded_content))

    logging.info(f"[CSV_UPLOAD] Raw CSV headers: {reader.fieldnames}")

    required_fields = ["symbol", "trade_date", "trade_type", "quantity", "price"]
    for field in required_fields:
        if field not in reader.fieldnames:
            avail = reader.fieldnames
            logging.warning(f"[CSV_UPLOAD] Missing column: {field}. Available: {avail}")
            raise HTTPException(
                status_code=400,
                detail=f"Missing required column: {field}",
            )

    row_num = 1
    errors = []
    skipped_no_trade_type = 0
    skipped_symbols = set()

    for row in reader:
        row_num += 1
        try:
            symbol = row.get("symbol", "").strip().upper()
            if not symbol:
                continue

            trade_type = row.get("trade_type", "").strip().upper()
            if trade_type not in ("BUY", "SELL"):
                skipped_no_trade_type += 1
                skipped_symbols.add(symbol)
                if skipped_no_trade_type <= 3:
                    raw = row.get("trade_type", "")
                    logging.warning(
                        f"[CSV_UPLOAD] Row {row_num}: skipped "
                        f"trade_type='{raw}' (normalized='{trade_type}') "
                        f"symbol={symbol}"
                    )
                continue

            trade_date = _normalize_trade_date(row.get("trade_date", "").strip())

            try:
                quantity = int(float(row.get("quantity", 0)))
            except (ValueError, TypeError):
                errors.append(f"Row {row_num}: Invalid quantity")
                skipped_symbols.add(symbol)
                continue

            try:
                price = float(row.get("price", 0))
            except (ValueError, TypeError):
                errors.append(f"Row {row_num}: Invalid price")
                skipped_symbols.add(symbol)
                continue

            trade = {
                "symbol": symbol,
                "isin": row.get("isin", "").strip() or None,
                "trade_date": trade_date,
                "exchange": row.get("exchange", "NSE").strip(),
                "segment": row.get("segment", "EQ").strip(),
                "series": row.get("series", "EQ").strip(),
                "side": trade_type,
                "quantity": quantity,
                "price": price,
                "trade_id": row.get("trade_id", "").strip() or None,
                "order_id": row.get("order_id", "").strip() or None,
                "order_execution_time": row.get("order_execution_time", "").strip() or None,
                "source": "zerodha_csv",
            }

            validation_err = _validate_trade(trade, row_num)
            if validation_err:
                errors.append(f"Row {row_num}: {validation_err}")
                skipped_symbols.add(symbol)
                continue

            trades.append(trade)
        except Exception as e:
            errors.append(f"Row {row_num}: {str(e)}")

    if skipped_no_trade_type > 0:
        logging.warning(
            f"[CSV_UPLOAD] {skipped_no_trade_type} rows skipped "
            f"due to invalid trade_type"
        )

    if not trades:
        logging.error(f"[CSV_UPLOAD] No valid trades parsed. Errors: {errors[:10]}")
        raise HTTPException(
            status_code=400,
            detail=f"No valid trades found. Errors: {errors[:5]}",
        )

    logging.info(
        f"[CSV_UPLOAD] Parsed {len(trades)} trades: "
        f"symbols={[t['symbol'] for t in trades]}, "
        f"sides={[t['side'] for t in trades]}, "
        f"dates={[t['trade_date'] for t in trades]}"
    )

    # Store in session cache
    context.session_cache.set_order_history(trades, source="zerodha_csv")

    # Store in database for persistence
    stored = _store_trades_in_db(
        user_id=current_user.user_id,
        session_id=session_id,
        broker=context.broker_name,
        trades=trades,
    )
    logging.info(
        f"[CSV_UPLOAD] Stored {stored} trades in DB: "
        f"user_id={current_user.user_id}, broker={context.broker_name}, session_id={session_id}"
    )

    oh_status = context.session_cache.get_order_history_status()

    return OrderHistoryStatusResponse(
        available=oh_status["available"],
        trade_count=oh_status["trade_count"],
        symbol_count=oh_status["symbol_count"],
        fetched_at=oh_status["fetched_at"].isoformat() if oh_status["fetched_at"] else None,
        source=oh_status["source"],
        date_from=oh_status.get("date_from"),
        date_to=oh_status.get("date_to"),
    )


@router.delete("/{session_id}/order-history")
def clear_order_history(
    session_id: str,
    current_user: UserContext = Depends(get_current_user),
    registry: SessionRegistry = Depends(get_session_registry),
):
    """Clear order history for this session."""
    registry.require_access(session_id, current_user)
    context = registry.get_session(session_id)
    if not context:
        raise HTTPException(status_code=404, detail="Session not found")

    # Clear from session cache
    context.session_cache.clear_order_history()

    # Clear from database
    _clear_trades_from_db(session_id=session_id)

    return {"message": "Order history cleared"}


DATE_FORMATS = [
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%Y-%m-%dT%H:%M:%S",
    "%d-%m-%YT%H:%M:%S",
]


def _normalize_trade_date(raw: str) -> str:
    """Parse a trade date string into YYYY-MM-DD format, or return as-is if unparseable."""
    raw_stripped = raw.strip()
    if not raw_stripped:
        return raw
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw_stripped, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw


def _validate_trade(trade: dict, row_num: int) -> Optional[str]:
    """Validate a parsed trade dict. Returns error message or None if valid."""
    errors = []

    sym = trade.get("symbol", "")
    clean = sym.replace("#", "").replace("-", "").upper()
    if not clean or not clean.isalnum():
        errors.append(f"Invalid symbol: '{sym}'")

    td = trade.get("trade_date", "")
    try:
        parsed = datetime.strptime(td, "%Y-%m-%d").date()
        if parsed > date.today():
            errors.append(f"Trade date in future: {td}")
        elif parsed < date(2000, 1, 1):
            errors.append(f"Trade date too old: {td}")
    except (ValueError, TypeError):
        errors.append(f"Unparseable trade_date: '{td}'")

    qty = trade.get("quantity", 0)
    if qty <= 0:
        errors.append(f"Quantity must be > 0, got {qty}")

    price = trade.get("price", 0)
    if price < 0:
        errors.append(f"Price must be >= 0, got {price}")

    side = trade.get("side", "")
    if side not in ("BUY", "SELL"):
        errors.append(f"Invalid side: '{side}'")

    return "; ".join(errors) if errors else None


def _store_trades_in_db(
    user_id: int,
    session_id: str,
    broker: str,
    trades: List[Dict],
) -> int:
    """Store trades in database, replacing existing session trades."""
    from datetime import datetime

    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    from db.database import SessionLocal
    from db.models import TradeSyncMetadata, UserTrade

    db = SessionLocal()
    try:
        stored_count = 0
        capture_source = trades[0].get("source", "unknown") if trades else "unknown"
        captured_at = datetime.now()

        for i, trade in enumerate(trades):
            trade_id = trade.get("trade_id")

            trade_data = {
                "user_id": user_id,
                "session_id": session_id,
                "broker": broker,
                "symbol": trade.get("symbol", ""),
                "isin": trade.get("isin"),
                "trade_date": trade.get("trade_date", ""),
                "exchange": trade.get("exchange", ""),
                "segment": trade.get("segment", ""),
                "series": trade.get("series", ""),
                "side": trade.get("side", ""),
                "quantity": trade.get("quantity", 0),
                "price": trade.get("price", 0),
                "trade_id": trade_id,
                "order_id": trade.get("order_id"),
                "order_execution_time": trade.get("order_execution_time"),
                "source": trade.get("source", "upload"),
                "captured_at": captured_at,
                "capture_source": capture_source,
            }

            # Use upsert pattern: INSERT ... ON CONFLICT DO UPDATE
            stmt = sqlite_insert(UserTrade).values(**trade_data)
            stmt = stmt.on_conflict_do_update(
                index_elements=["user_id", "broker", "trade_id"],
                set_={
                    "session_id": session_id,
                    "symbol": trade.get("symbol", ""),
                    "isin": trade.get("isin"),
                    "trade_date": trade.get("trade_date", ""),
                    "exchange": trade.get("exchange", ""),
                    "segment": trade.get("segment", ""),
                    "series": trade.get("series", ""),
                    "side": trade.get("side", ""),
                    "quantity": trade.get("quantity", 0),
                    "price": trade.get("price", 0),
                    "order_id": trade.get("order_id"),
                    "order_execution_time": trade.get("order_execution_time"),
                    "source": trade.get("source", "upload"),
                    "captured_at": captured_at,
                    "capture_source": capture_source,
                },
            )
            db.execute(stmt)
            stored_count += 1

        db.commit()

        # Update sync metadata
        sync_meta = db.query(TradeSyncMetadata).filter(
            TradeSyncMetadata.user_id == user_id,
            TradeSyncMetadata.broker == broker,
        ).first()

        if sync_meta:
            sync_meta.last_capture_date = datetime.now().date()
            sync_meta.last_capture_trade_count = stored_count
            sync_meta.last_updated_at = captured_at
        else:
            sync_meta = TradeSyncMetadata(
                user_id=user_id,
                broker=broker,
                last_capture_date=datetime.now().date(),
                last_capture_trade_count=stored_count,
                last_updated_at=captured_at,
            )
            db.add(sync_meta)

        db.commit()

        return stored_count
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to store trades in DB: {type(e).__name__}: {e}")
        for i, trade in enumerate(trades[:3]):
            logging.error(f"Trade {i}: trade_id={trade.get('trade_id')}, symbol={trade.get('symbol')}")
        raise e
    finally:
        db.close()


def _load_trades_from_db(session_id: str) -> List[Dict]:
    """Load trades from database for a session."""
    from db.database import SessionLocal
    from db.models import UserTrade

    db = SessionLocal()
    try:
        trades = db.query(UserTrade).filter(
            UserTrade.session_id == session_id
        ).all()

        return [
            {
                "symbol": t.symbol,
                "isin": t.isin,
                "trade_date": t.trade_date,
                "exchange": t.exchange,
                "segment": t.segment,
                "series": t.series,
                "side": t.side,
                "quantity": t.quantity,
                "price": t.price,
                "trade_id": t.trade_id,
                "order_id": t.order_id,
                "order_execution_time": t.order_execution_time,
                "source": t.source,
            }
            for t in trades
        ]
    finally:
        db.close()


def _load_trades_by_user(user_id: int, broker: str) -> List[Dict]:
    """Load trades from database for a user+broker combination (premium persistence)."""
    from db.database import SessionLocal
    from db.models import UserTrade

    db = SessionLocal()
    try:
        trades = db.query(UserTrade).filter(
            UserTrade.user_id == user_id,
            UserTrade.broker == broker,
        ).all()

        return [
            {
                "symbol": t.symbol,
                "isin": t.isin,
                "trade_date": t.trade_date,
                "exchange": t.exchange,
                "segment": t.segment,
                "series": t.series,
                "side": t.side,
                "quantity": t.quantity,
                "price": t.price,
                "trade_id": t.trade_id,
                "order_id": t.order_id,
                "order_execution_time": t.order_execution_time,
                "source": t.source,
            }
            for t in trades
        ]
    finally:
        db.close()


def _update_trades_session_id(user_id: int, broker: str, new_session_id: str) -> int:
    """Update session_id on all trades for a user+broker to a new session."""
    from db.database import SessionLocal
    from db.models import UserTrade

    db = SessionLocal()
    try:
        count = db.query(UserTrade).filter(
            UserTrade.user_id == user_id,
            UserTrade.broker == broker,
        ).update({"session_id": new_session_id})
        db.commit()
        return count
    finally:
        db.close()


def _clear_trades_from_db(session_id: str) -> int:
    """Clear trades from database for a session."""
    from db.database import SessionLocal
    from db.models import UserTrade

    db = SessionLocal()
    try:
        count = db.query(UserTrade).filter(
            UserTrade.session_id == session_id
        ).delete()
        db.commit()
        return count
    finally:
        db.close()


@router.post("/{session_id}/wroi-trend")
def compute_wroi_trend(
    session_id: str,
    current_user: UserContext = Depends(get_current_user),
    registry: SessionRegistry = Depends(get_session_registry),
):
    """
    Compute WROI capital efficiency trend and exit scores for each holding.

    Uses OHLCV history to calculate:
    - WROI trend: how each holding's weighted ROI has moved over time.
    - Exit score: EMA structure (50 pts), volume (30 pts), WROI trend (20 pts).
    - Sub-scores (ema_score, volume_score, wroi_score) for UI breakdown.

    Requires OHLCV data via the Upstox analytics token.
    Computation runs inline and may take a few seconds while OHLCV is being fetched.
    """
    from core.exit_scorer import compute_exit_scores
    from core.holdings import HoldingsAnalyzer
    from core.market_data.ohlcv_store import get_ohlcv_multi
    from core.wroi_trend import compute_wroi_trends

    context = registry.require_access(session_id, current_user)
    if not context:
        raise HTTPException(
            status_code=401,
            detail="Session expired. Please restart your session from the Sessions page.",
        )

    context.session_cache.refresh_all_caches()

    holdings_analyzer = HoldingsAnalyzer(
        context.broker_user_id,
        context.broker_name,
        context.user_record_id,
    )
    results = holdings_analyzer.analyze_holdings(
        context.broker, context.session_cache.get_cmp_manager()
    )

    symbols = list(set(
        h.get("symbol", "").replace("-BE", "").replace("#", "").upper()
        for h in results
    ))
    symbols = [s for s in symbols if s]

    if not symbols:
        return {"wroi_trends": {}, "scores": {}}

    logger.info(f"Ensuring OHLCV data for {len(symbols)} symbols...")
    from core.services.ohlcv_refresh_service import OhlcvRefreshService

    ohlcv_svc = OhlcvRefreshService()
    warnings: List[str] = []

    initial_result = ohlcv_svc.refresh_for_symbols(symbols, days=90)
    if initial_result.get("symbols_failed", 0) > 0:
        failed = initial_result["symbols_failed"]
        warnings.append(f"OHLCV refresh failed for {failed} symbol(s)")
        logger.warning("OHLCV initial refresh: %d symbols failed", failed)

    ohlcv_data = get_ohlcv_multi(symbols, days=90)

    # Force-refresh OHLCV for symbols with stale data (latest candle >5 days old)
    # or legacy NULL volume (pre-c[5] is not None fix)
    stale_symbols = []
    for sym, candles in ohlcv_data.items():
        if not candles:
            stale_symbols.append(sym)
        else:
            latest = candles[-1]
            latest_date = latest.get("trade_date")
            if latest_date and (date.today() - latest_date).days > 5:
                stale_symbols.append(sym)
            elif latest.get("volume") is None:
                stale_symbols.append(sym)

    if stale_symbols:
        logger.info(
            "Force-refreshing OHLCV for %d symbols with stale data",
            len(stale_symbols),
        )
        force_result = ohlcv_svc.refresh_for_symbols(
            stale_symbols, days=90, force_refresh=True
        )
        if force_result.get("symbols_failed", 0) > 0:
            failed = force_result["symbols_failed"]
            warnings.append(f"Forced OHLCV refresh failed for {failed} symbol(s)")
            logger.warning("OHLCV force-refresh: %d symbols failed", failed)
        fresh_ohlcv = get_ohlcv_multi(stale_symbols, days=90)
        ohlcv_data.update(fresh_ohlcv)

    # ── Compute and persist thesis_break_price for each holding's entry strategy ──
    from core.services.thesis_break import get_thesis_break_service
    from db.database import SessionLocal
    from db.models import EntryLevel, EntryStrategy

    thesis_svc = get_thesis_break_service()
    db = SessionLocal()
    try:
        strategies = db.query(EntryStrategy).filter(
            EntryStrategy.user_id == context.user_record_id,
            EntryStrategy.broker == context.broker_name,
        ).all()

        strategy_by_symbol: Dict[str, EntryStrategy] = {}
        for s in strategies:
            key = s.symbol.replace("-BE", "").replace("#", "").upper()
            strategy_by_symbol[key] = s

        for sym_clean in symbols:
            strategy = strategy_by_symbol.get(sym_clean)
            if not strategy:
                continue

            candles = ohlcv_data.get(sym_clean, [])
            if not candles or len(candles) < 20:
                continue

            levels = (
                db.query(EntryLevel)
                .filter(EntryLevel.strategy_id == strategy.id)
                .filter(EntryLevel.is_active.is_(True))
                .order_by(EntryLevel.level_no)
                .all()
            )
            entry3_price = None
            for level in levels:
                if level.level_no == 3:
                    entry3_price = level.price
            if entry3_price is None and levels:
                entry3_price = levels[-1].price

            if entry3_price:
                tb_price = thesis_svc.calculate(strategy.symbol, entry3_price, candles)
                if tb_price is not None:
                    strategy.thesis_break_price = tb_price

            # Cleanup old THESIS_BREAK review_status from entry strategies
            if strategy.review_status == "THESIS_BREAK":
                strategy.review_status = "ACTIVE"

        # Clear stale thesis_break_price for symbols no longer in holdings
        for sym_clean, strategy in strategy_by_symbol.items():
            if sym_clean not in symbols and strategy.thesis_break_price is not None:
                strategy.thesis_break_price = None

        db.commit()

        # Extract scalar values before closing the session to avoid detached instance access
        thesis_break_map: Dict[str, float | None] = {
            sym: strategy_by_symbol[sym].thesis_break_price
            for sym in strategy_by_symbol
        }
    finally:
        db.close()

    # Re-check thesis break against freshly computed values on result dicts
    for h in results:
        sym_clean = h.get("symbol", "").replace("-BE", "").replace("#", "").upper()
        tb_price = thesis_break_map.get(sym_clean)
        if tb_price is None:
            continue
        ltp = h.get("last_price")
        if ltp and ltp <= tb_price:
            h["thesis_broken"] = True
            h["thesis_break_price"] = tb_price
            h["thesis_break_pct"] = round((ltp - tb_price) / tb_price * 100, 2)

    total_invested = sum(h.get("invested", 0) for h in results)

    # WROI trends
    trends = compute_wroi_trends(results, ohlcv_data, total_invested)

    # Exit scores (pass pre-computed trends to avoid duplicate work)
    compute_exit_scores(results, ohlcv_data, total_invested, wroi_trends=trends)

    # Build per-symbol score map
    scores: Dict[str, Dict] = {}
    for h in results:
        sym = h.get("symbol", "")
        sym_clean = sym.replace("-BE", "").replace("#", "").upper()
        scores[sym] = {
            "exit_score": h.get("exit_score"),
            "exit_action": h.get("exit_action"),
            "ema_score": h.get("ema_score"),
            "volume_score": h.get("volume_score"),
            "wroi_score": h.get("wroi_score"),
            "wroi_trend": trends.get(sym_clean, "NA"),
        }

    result: Dict[str, Any] = {"wroi_trends": trends, "scores": scores}
    if warnings:
        result["warnings"] = warnings
    return result


def load_session_order_history(context) -> None:
    """
    Load order history from database into session cache.
    Called when session is accessed to restore persisted order history.
    """
    trades = _load_trades_from_db(context.session_id)
    if trades:
        # Determine source from first trade
        source = trades[0].get("source", "unknown") if trades else None
        context.session_cache.set_order_history(trades, source=source)
