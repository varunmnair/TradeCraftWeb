"""OHLCV store - Single Source of Truth for historical price data."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Dict, List, Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from db.database import SessionLocal
from db.models import OhlcvDaily

LOGGER = logging.getLogger("tradecraftx.ohlcv_store")

MAX_RETURNED_CANDLES = 500


class OhlcvStoreError(Exception):
    """Raised when OHLCV data is not available."""

    pass


def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_ohlcv(
    symbol: str,
    days: int = 200,
    db: Optional[Session] = None,
) -> List[Dict]:
    """Get OHLCV data for a symbol.

    Args:
        symbol: Stock symbol (e.g., 'RELIANCE')
        days: Number of calendar days to fetch (default 200)
        db: Optional database session

    Returns:
        List of candles sorted by date ascending.
        Each candle: {"trade_date": date, "open": float, "high": float, "low": float, "close": float, "volume": int}

    Raises:
        OhlcvStoreError: If no data is found in the database.
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        cutoff = date.today() - timedelta(days=days)

        candles = (
            db.query(OhlcvDaily)
            .filter(
                and_(
                    OhlcvDaily.symbol == symbol.upper(),
                    OhlcvDaily.trade_date >= cutoff,
                )
            )
            .order_by(OhlcvDaily.trade_date)
            .limit(MAX_RETURNED_CANDLES)
            .all()
        )

        if not candles:
            raise OhlcvStoreError(
                f"No OHLCV data found for {symbol}. "
                f"Admin may need to run OHLCV refresh from Market Data page."
            )

        return [
            {
                "trade_date": c.trade_date,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in candles
        ]
    finally:
        if should_close:
            db.close()


def get_ohlcv_multi(
    symbols: List[str],
    days: int = 200,
    db: Optional[Session] = None,
) -> Dict[str, List[Dict]]:
    """Get OHLCV data for multiple symbols.

    Args:
        symbols: List of stock symbols
        days: Number of calendar days to fetch (default 200)
        db: Optional database session

    Returns:
        Dict mapping symbol to list of candles.
        Missing symbols will have empty lists.
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        cutoff = date.today() - timedelta(days=days)
        symbols_upper = [s.upper() for s in symbols]

        candles = (
            db.query(OhlcvDaily)
            .filter(
                and_(
                    OhlcvDaily.symbol.in_(symbols_upper),
                    OhlcvDaily.trade_date >= cutoff,
                )
            )
            .order_by(OhlcvDaily.symbol, OhlcvDaily.trade_date)
            .all()
        )

        result = {s.upper(): [] for s in symbols}
        for c in candles:
            result[c.symbol].append(
                {
                    "trade_date": c.trade_date,
                    "open": c.open,
                    "high": c.high,
                    "low": c.low,
                    "close": c.close,
                    "volume": c.volume,
                }
            )

        return result
    finally:
        if should_close:
            db.close()


def get_latest_date(symbol: str, db: Optional[Session] = None) -> Optional[date]:
    """Get the latest date for which OHLCV data exists for a symbol."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        return (
            db.query(func.max(OhlcvDaily.trade_date))
            .filter(OhlcvDaily.symbol == symbol.upper())
            .scalar()
        )
    finally:
        if should_close:
            db.close()


def get_stats(db: Optional[Session] = None) -> Dict:
    """Get OHLCV coverage statistics."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        total_candles = db.query(func.count(OhlcvDaily.symbol)).scalar() or 0
        symbols_count = (
            db.query(func.count(func.distinct(OhlcvDaily.symbol))).scalar() or 0
        )
        latest_date = db.query(func.max(OhlcvDaily.trade_date)).scalar()

        return {
            "total_candles": total_candles,
            "symbols_count": symbols_count,
            "latest_date": latest_date,
        }
    finally:
        if should_close:
            db.close()
