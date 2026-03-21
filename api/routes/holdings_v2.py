from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from api.dependencies import get_current_user, get_session_registry
from core.auth.context import UserContext
from core.runtime.session_registry import SessionRegistry

logger = logging.getLogger("tradecraftx.holdings")


router = APIRouter(prefix="/holdings", tags=["holdings"])


class OrderHistoryStatusResponse(BaseModel):
    available: bool
    trade_count: int
    symbol_count: int
    fetched_at: Optional[str]
    source: Optional[str]


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
    Holdings are fetched fresh from the broker.
    Order history fields are populated if order history has been fetched.
    """
    registry.require_access(session_id, current_user)
    context = registry.get_session(session_id)
    if not context:
        raise HTTPException(status_code=404, detail="Session not found")

    # Refresh holdings from broker
    context.session_cache.refresh_holdings()
    
    # Get enriched holdings with order history data
    holdings = context.session_cache.get_holdings_enriched()
    
    # Get order history status
    oh_status = context.session_cache.get_order_history_status()
    
    return HoldingsResponse(
        session_id=session_id,
        broker=context.broker_name,
        broker_user_id=context.broker_user_id or "",
        holdings=holdings,
        order_history=OrderHistoryStatusResponse(
            available=oh_status["available"],
            trade_count=oh_status["trade_count"],
            symbol_count=oh_status["symbol_count"],
            fetched_at=oh_status["fetched_at"].isoformat() if oh_status["fetched_at"] else None,
            source=oh_status["source"],
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
    )


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
        to_date = datetime.now()
        from_date = to_date - timedelta(days=payload.days)
        
        orders = context.broker.get_orders(
            segment="EQUITY",
            from_date=from_date.strftime("%Y-%m-%d"),
            to_date=to_date.strftime("%Y-%m-%d"),
        )
        
        # Convert orders to trade format
        trades = []
        for order in orders:
            trade_date = order.get("fill_timestamp") or order.get("order_date")
            if isinstance(trade_date, datetime):
                trade_date = trade_date.strftime("%Y-%m-%d")
            
            trades.append({
                "symbol": order.get("tradingsymbol", "").strip().upper(),
                "isin": None,
                "trade_date": trade_date,
                "exchange": order.get("exchange", "NSE"),
                "segment": order.get("segment", "EQ"),
                "series": order.get("series", "EQ"),
                "side": "BUY" if order.get("transaction_type") == "BUY" else "SELL",
                "quantity": order.get("filled_quantity", 0),
                "price": order.get("average_price", 0),
                "trade_id": order.get("order_id"),
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
        )
        
    except Exception as e:
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
    
    required_fields = ["symbol", "trade_date", "trade_type", "quantity", "price"]
    for field in required_fields:
        if field not in reader.fieldnames:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required column: {field}",
            )
    
    row_num = 1
    errors = []
    
    for row in reader:
        row_num += 1
        try:
            symbol = row.get("symbol", "").strip().upper()
            if not symbol:
                continue
            
            trade_type = row.get("trade_type", "").strip().upper()
            if trade_type not in ("BUY", "SELL"):
                continue  # Skip invalid trade types
            
            trade_date = row.get("trade_date", "").strip()
            
            try:
                quantity = int(float(row.get("quantity", 0)))
            except (ValueError, TypeError):
                errors.append(f"Row {row_num}: Invalid quantity")
                continue
                
            try:
                price = float(row.get("price", 0))
            except (ValueError, TypeError):
                errors.append(f"Row {row_num}: Invalid price")
                continue
            
            trades.append({
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
            })
        except Exception as e:
            errors.append(f"Row {row_num}: {str(e)}")
    
    if not trades:
        raise HTTPException(
            status_code=400,
            detail=f"No valid trades found. Errors: {errors[:5]}",
        )
    
    # Store in session cache
    context.session_cache.set_order_history(trades, source="zerodha_csv")
    
    # Store in database for persistence
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


def _store_trades_in_db(
    user_id: int,
    session_id: str,
    broker: str,
    trades: List[Dict],
) -> int:
    """Store trades in database, replacing existing session trades."""
    from db.database import SessionLocal
    from db.models import UserTrade
    
    db = SessionLocal()
    try:
        # Delete existing trades for this session
        db.query(UserTrade).filter(
            UserTrade.session_id == session_id
        ).delete()
        
        # Insert new trades
        for trade in trades:
            db.add(UserTrade(
                user_id=user_id,
                session_id=session_id,
                broker=broker,
                symbol=trade.get("symbol", ""),
                isin=trade.get("isin"),
                trade_date=trade.get("trade_date", ""),
                exchange=trade.get("exchange", ""),
                segment=trade.get("segment", ""),
                series=trade.get("series", ""),
                side=trade.get("side", ""),
                quantity=trade.get("quantity", 0),
                price=trade.get("price", 0),
                trade_id=trade.get("trade_id"),
                order_id=trade.get("order_id"),
                order_execution_time=trade.get("order_execution_time"),
                source=trade.get("source", "upload"),
            ))
        
        db.commit()
        return len(trades)
    except Exception as e:
        db.rollback()
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
