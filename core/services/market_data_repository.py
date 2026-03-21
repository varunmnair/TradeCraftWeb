"""Market data repository for app-level storage of CMP and candles."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Dict, List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from db.database import SessionLocal
from db.models import MarketCandleDaily, MarketQuoteDaily, MarketUniverse

LOGGER = logging.getLogger("tradecraftx.market_data")


class MarketDataRepository:
    def __init__(self, db: Session):
        self._db = db

    def get_universe_symbols(
        self, universe: str = "NIFTY500", enabled_only: bool = True
    ) -> List[str]:
        query = self._db.query(MarketUniverse.symbol)
        if enabled_only:
            query = query.filter(MarketUniverse.enabled.is_(True))
        query = query.filter(MarketUniverse.universe == universe)
        return [row[0] for row in query.all()]

    def get_universe_count(
        self, universe: str = "NIFTY500", enabled_only: bool = True
    ) -> int:
        query = self._db.query(MarketUniverse)
        if enabled_only:
            query = query.filter(MarketUniverse.enabled.is_(True))
        query = query.filter(MarketUniverse.universe == universe)
        return query.count()

    def set_universe_symbols(
        self, symbols: List[str], universe: str = "NIFTY500"
    ) -> int:
        count = 0
        existing_symbols = set(
            row[0] for row in self._db.query(MarketUniverse.symbol).all()
        )
        for sym in symbols:
            if sym not in existing_symbols:
                self._db.add(
                    MarketUniverse(symbol=sym, universe=universe, enabled=True)
                )
                existing_symbols.add(sym)
                count += 1
        self._db.commit()
        return count

    def reset_universe_symbols(self, universe: str = "NIFTY500") -> int:
        deleted = (
            self._db.query(MarketUniverse)
            .filter(MarketUniverse.universe == universe)
            .delete()
        )
        self._db.commit()
        return deleted

    def get_quotes_for_symbols(
        self, symbols: List[str], trade_date: Optional[str] = None
    ) -> Dict[str, Optional[Dict]]:
        if not symbols:
            return {}
        if trade_date is None:
            trade_date = date.today().strftime("%Y-%m-%d")

        rows = (
            self._db.query(MarketQuoteDaily)
            .filter(
                and_(
                    MarketQuoteDaily.symbol.in_(symbols),
                    MarketQuoteDaily.trade_date == trade_date,
                )
            )
            .all()
        )

        result = {}
        for row in rows:
            result[row.symbol] = {
                "cmp": row.cmp,
                "as_of_ts": row.as_of_ts.isoformat() if row.as_of_ts else None,
                "source": row.source,
            }
        for sym in symbols:
            if sym not in result:
                result[sym] = None
        return result

    def upsert_quotes(
        self, quotes: Dict[str, float], trade_date: str, source: str = "manual"
    ) -> int:
        count = 0
        for sym, cmp in quotes.items():
            existing = (
                self._db.query(MarketQuoteDaily)
                .filter(
                    and_(
                        MarketQuoteDaily.symbol == sym,
                        MarketQuoteDaily.trade_date == trade_date,
                    )
                )
                .first()
            )
            if existing:
                existing.cmp = cmp
                existing.as_of_ts = datetime.now()
                existing.source = source
            else:
                self._db.add(
                    MarketQuoteDaily(
                        symbol=sym,
                        trade_date=trade_date,
                        cmp=cmp,
                        as_of_ts=datetime.now(),
                        source=source,
                    )
                )
            count += 1
        self._db.commit()
        return count

    def get_candles_for_symbols(
        self, symbols: List[str], days: int = 400
    ) -> Dict[str, List[Dict]]:
        if not symbols:
            return {}

        cutoff_date = date.today()
        for _ in range(days + 30):
            if cutoff_date.weekday() < 5:
                break
            from datetime import timedelta

            cutoff_date = cutoff_date - timedelta(days=1)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")

        rows = (
            self._db.query(MarketCandleDaily)
            .filter(
                and_(
                    MarketCandleDaily.symbol.in_(symbols),
                    MarketCandleDaily.trade_date >= cutoff_str,
                )
            )
            .order_by(MarketCandleDaily.symbol, MarketCandleDaily.trade_date)
            .all()
        )

        result = {sym: [] for sym in symbols}
        for row in rows:
            if row.close is not None:
                result[row.symbol].append(
                    {
                        "trade_date": row.trade_date,
                        "open": row.open,
                        "high": row.high,
                        "low": row.low,
                        "close": row.close,
                        "volume": row.volume,
                    }
                )

        return result

    def _get_last_candle_dates(self, symbols: List[str]) -> Dict[str, Optional[date]]:
        from sqlalchemy import func

        if not symbols:
            return {}

        rows = (
            self._db.query(
                MarketCandleDaily.symbol,
                func.max(MarketCandleDaily.trade_date).label("last_date"),
            )
            .filter(
                and_(
                    MarketCandleDaily.symbol.in_(symbols),
                    MarketCandleDaily.close.isnot(None),
                )
            )
            .group_by(MarketCandleDaily.symbol)
            .all()
        )

        result = {}
        for row in rows:
            if row.last_date:
                result[row.symbol] = date.fromisoformat(row.last_date)
        return result

    def upsert_candles(
        self, candles: Dict[str, List[Dict]], source: str = "manual"
    ) -> int:
        count = 0
        LOGGER.info(
            f"[upsert_candles] Starting with {len(candles)} symbols: {list(candles.keys())[:5]}..."
        )
        for sym, candle_list in candles.items():
            LOGGER.info(
                f"[upsert_candles] Processing {sym}: {len(candle_list)} candles"
            )
            for c in candle_list:
                trade_date = c.get("trade_date")
                if not trade_date:
                    LOGGER.warning(
                        f"[upsert_candles] Skipping candle for {sym} - no trade_date"
                    )
                    continue
                existing = (
                    self._db.query(MarketCandleDaily)
                    .filter(
                        and_(
                            MarketCandleDaily.symbol == sym,
                            MarketCandleDaily.trade_date == trade_date,
                        )
                    )
                    .first()
                )
                if existing:
                    existing.open = c.get("open")
                    existing.high = c.get("high")
                    existing.low = c.get("low")
                    existing.close = c.get("close")
                    existing.volume = c.get("volume")
                    existing.source = source
                    LOGGER.debug(f"[upsert_candles] Updated {sym} on {trade_date}")
                else:
                    self._db.add(
                        MarketCandleDaily(
                            symbol=sym,
                            trade_date=trade_date,
                            open=c.get("open"),
                            high=c.get("high"),
                            low=c.get("low"),
                            close=c.get("close"),
                            volume=c.get("volume"),
                            source=source,
                        )
                    )
                    LOGGER.debug(f"[upsert_candles] Added {sym} on {trade_date}")
                count += 1
        LOGGER.info(f"[upsert_candles] Prepared {count} candles for commit")
        try:
            self._db.commit()
            LOGGER.info(
                f"[upsert_candles] SUCCESS: Committed {count} candles for {list(candles.keys())}"
            )
        except Exception as e:
            LOGGER.error(f"[upsert_candles] FAILED: Error committing candles: {e}")
            self._db.rollback()
        return count


def get_repository() -> MarketDataRepository:
    db = SessionLocal()
    return MarketDataRepository(db)
