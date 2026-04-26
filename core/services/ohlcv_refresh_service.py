"""OHLCV refresh service for fetching and storing daily candles."""

from __future__ import annotations

import logging
import os
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from core.session_manager import SessionManager

LOGGER = logging.getLogger("tradecraftx.ohlcv_refresh")

BATCH_SIZE = 50
SLEEP_BETWEEN_BATCHES = 0.5
SKIP_HOURS = 24


class OhlcvRefreshService:
    def __init__(
        self,
        session_manager: Optional[SessionManager] = None,
        connection_id: Optional[int] = None,
    ):
        self._session_manager = session_manager
        self._connection_id = connection_id

    def get_config_days(self) -> int:
        from db.database import SessionLocal
        from db.models import OhlcvConfig

        db = SessionLocal()
        try:
            config = db.query(OhlcvConfig).first()
            return config.days if config else 200
        finally:
            db.close()

    def set_config_days(self, days: int) -> None:
        from db.database import SessionLocal
        from db.models import OhlcvConfig

        db = SessionLocal()
        try:
            config = db.query(OhlcvConfig).first()
            if config:
                config.days = days
                config.updated_at = datetime.now(timezone.utc)
            else:
                config = OhlcvConfig(days=days, updated_at=datetime.now(timezone.utc))
                db.add(config)
            db.commit()
        finally:
            db.close()

    def refresh_for_symbols(
        self,
        symbols: List[str],
        days: Optional[int] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        if not symbols:
            return {
                "operation": "ohlcv_refresh_symbols",
                "symbols_requested": 0,
                "symbols_skipped": 0,
                "symbols_refreshed": 0,
                "symbols_failed": 0,
                "failures": [],
            }

        if days is None:
            days = self.get_config_days()

        LOGGER.info(f"=== Starting OHLCV refresh for {len(symbols)} symbols (days={days}) ===")

        token = os.environ.get("UPSTOX_ANALYTICS_TOKEN")
        if not token:
            LOGGER.error("UPSTOX_ANALYTICS_TOKEN not configured")
            return {
                "operation": "ohlcv_refresh_symbols",
                "symbols_requested": len(symbols),
                "symbols_skipped": 0,
                "symbols_refreshed": 0,
                "symbols_failed": len(symbols),
                "failures": [
                    {"symbol": s, "excerpt": "UPSTOX_ANALYTICS_TOKEN not configured"}
                    for s in symbols[:100]
                ],
            }

        from core.services.symbol_catalog_repository import SymbolCatalogRepository
        from db.database import SessionLocal

        db = SessionLocal()
        try:
            repo = SymbolCatalogRepository(db)
            all_symbols_data = repo.get_all_for_cmp_refresh()
            symbols_set = set(s.upper() for s in symbols)  # {'BEL', 'SBIN'}
            symbol_map = {}
            for item in all_symbols_data:
                sym = item.get("symbol", "").upper()
                if sym in symbols_set:
                    isin = item.get("isin", "")
                    exchange = item.get("exchange", "NSE").upper()
                    series = item.get("series", "EQ").upper()
                    segment = f"{exchange}_{series}"
                    if isin and segment in {"NSE_EQ", "BSE_EQ"}:
                        symbol_map[sym] = {
                            "exchange": exchange,
                            "series": series,
                            "instrument_key": f"{segment}|{isin}",
                        }
        finally:
            db.close()

        LOGGER.info(f"Found instrument keys for {len(symbol_map)} symbols")

        symbols_skipped = 0
        symbols_refreshed = 0
        symbols_failed = 0
        failures: List[Dict] = []

        today = date.today()
        window_start = today - timedelta(days=days)

        symbols_to_fetch = []
        for symbol in symbols:
            sym_upper = symbol.upper()
            info = symbol_map.get(sym_upper)

            if not info:
                LOGGER.debug(f"[{symbol}] No instrument key found, skipping")
                symbols_skipped += 1
                continue

            db = SessionLocal()
            try:
                should_refresh = self._should_refresh_symbol(
                    db, sym_upper, force_refresh
                )
            finally:
                db.close()

            if not should_refresh:
                LOGGER.debug(f"[{symbol}] Skipped - refreshed within {SKIP_HOURS} hours")
                symbols_skipped += 1
                continue

            symbols_to_fetch.append((sym_upper, info))

        LOGGER.info(f"Need to refresh {len(symbols_to_fetch)} symbols")

        for i in range(0, len(symbols_to_fetch), BATCH_SIZE):
            batch = symbols_to_fetch[i : i + BATCH_SIZE]
            LOGGER.info(f"Processing batch {i + 1}-{min(i + BATCH_SIZE, len(symbols_to_fetch))}")

            for symbol, info in batch:
                result = self._refresh_single_symbol(
                    symbol=symbol,
                    instrument_key=info["instrument_key"],
                    token=token,
                    days=days,
                    today=today,
                    window_start=window_start,
                )

                if result["status"] == "skipped":
                    symbols_skipped += 1
                elif result["status"] == "success":
                    symbols_refreshed += 1
                else:
                    symbols_failed += 1
                    failures.append({"symbol": symbol, "excerpt": result.get("error", "Unknown error")})

            if i + BATCH_SIZE < len(symbols_to_fetch):
                time.sleep(SLEEP_BETWEEN_BATCHES)

        LOGGER.info(
            f"=== OHLCV refresh complete: {symbols_refreshed} refreshed, "
            f"{symbols_skipped} skipped, {symbols_failed} failed ==="
        )

        return {
            "operation": "ohlcv_refresh_symbols",
            "symbols_requested": len(symbols),
            "symbols_skipped": symbols_skipped,
            "symbols_refreshed": symbols_refreshed,
            "symbols_failed": symbols_failed,
            "failures": failures[:100],
        }

    def _should_refresh_symbol(
        self, db: Session, symbol: str, force_refresh: bool
    ) -> bool:
        from db.models import OhlcvMetadata, OhlcvDaily

        if force_refresh:
            return True

        metadata = (
            db.query(OhlcvMetadata)
            .filter(OhlcvMetadata.symbol == symbol)
            .first()
        )

        if not metadata:
            return True

        # Check if actual candle data exists in ohlcv_daily
        candle_count = (
            db.query(func.count(OhlcvDaily.id))
            .filter(OhlcvDaily.symbol == symbol)
            .scalar()
        ) or 0

        if candle_count == 0:
            # No candle data exists - force refresh
            LOGGER.info(f"[{symbol}] No candle data found, forcing refresh")
            return True

        last_fetched = metadata.last_fetched_at
        if last_fetched.tzinfo is None:
            last_fetched = last_fetched.replace(tzinfo=timezone.utc)
        hours_since = (datetime.now(timezone.utc) - last_fetched).total_seconds() / 3600
        return hours_since >= SKIP_HOURS

    def _get_fetch_range(
        self, db: Session, symbol: str, today: date, window_start: date
    ) -> tuple[Optional[date], Optional[date]]:
        from db.models import OhlcvDaily

        max_date = (
            db.query(func.max(OhlcvDaily.trade_date))
            .filter(OhlcvDaily.symbol == symbol)
            .scalar()
        )

        if max_date is None:
            return window_start, today

        if max_date >= today - timedelta(days=1):
            return None, None

        return max_date + timedelta(days=1), today

    def _refresh_single_symbol(
        self,
        symbol: str,
        instrument_key: str,
        token: str,
        days: int,
        today: date,
        window_start: date,
    ) -> Dict[str, Any]:
        from datetime import datetime, timezone
        from db.database import SessionLocal
        from db.models import OhlcvDaily, OhlcvMetadata

        db = SessionLocal()
        try:
            from_date, to_date = self._get_fetch_range(db, symbol, today, window_start)

            if from_date is None and to_date is None:
                return {"status": "skipped", "reason": "Already up to date"}

            result = self._fetch_and_store(
                db=db,
                symbol=symbol,
                instrument_key=instrument_key,
                token=token,
                from_date=from_date,
                to_date=to_date,
                window_start=window_start,
            )

            if result["success"]:
                self._update_metadata(db, symbol, days)
                self._cleanup_old_data(db, symbol, window_start)
                return {
                    "status": "success",
                    "candles_upserted": result.get("upserted", 0),
                    "candles_deleted": result.get("deleted", 0),
                }
            else:
                return {"status": "error", "error": result.get("error", "Unknown error")}

        finally:
            db.close()

    def _fetch_and_store(
        self,
        db: Session,
        symbol: str,
        instrument_key: str,
        token: str,
        from_date: date,
        to_date: date,
        window_start: date,
    ) -> Dict[str, Any]:
        import requests

        from db.models import OhlcvDaily

        url = (
            f"https://api.upstox.com/v2/historical-candle/{instrument_key}/day/"
            f"{to_date.strftime('%Y-%m-%d')}/{from_date.strftime('%Y-%m-%d')}"
        )

        try:
            response = requests.get(
                url,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("status") != "success":
                    return {"success": False, "error": f"API error: {data.get('status')}"}

                candles_raw = data.get("data", {}).get("candles", [])
                if not candles_raw:
                    return {"success": False, "error": "No candles in response"}

                existing_dates: set = set(
                    d[0]
                    for d in db.query(OhlcvDaily.trade_date)
                    .filter(
                        OhlcvDaily.symbol == symbol,
                        OhlcvDaily.trade_date >= from_date,
                        OhlcvDaily.trade_date <= to_date,
                    )
                    .all()
                )

                upserted = 0
                for c in candles_raw:
                    if len(c) >= 5:
                        trade_date_str = str(c[0])[:10]
                        try:
                            trade_date = date.fromisoformat(trade_date_str)
                        except ValueError:
                            continue

                        if trade_date in existing_dates:
                            existing = (
                                db.query(OhlcvDaily)
                                .filter(
                                    and_(
                                        OhlcvDaily.symbol == symbol,
                                        OhlcvDaily.trade_date == trade_date,
                                    )
                                )
                                .first()
                            )
                            if existing:
                                existing.open = float(c[1]) if c[1] else None
                                existing.high = float(c[2]) if c[2] else None
                                existing.low = float(c[3]) if c[3] else None
                                existing.close = float(c[4]) if c[4] else None
                                existing.volume = int(c[5]) if len(c) > 5 and c[5] else None
                        else:
                            db.add(
                                OhlcvDaily(
                                    symbol=symbol,
                                    trade_date=trade_date,
                                    open=float(c[1]) if c[1] else None,
                                    high=float(c[2]) if c[2] else None,
                                    low=float(c[3]) if c[3] else None,
                                    close=float(c[4]) if c[4] else None,
                                    volume=int(c[5]) if len(c) > 5 and c[5] else None,
                                )
                            )
                            existing_dates.add(trade_date)
                        upserted += 1

                db.commit()
                return {"success": True, "upserted": upserted, "deleted": 0}

            elif response.status_code == 400:
                return {"success": False, "error": "Invalid instrument or date range"}
            elif response.status_code == 404:
                return {"success": False, "error": "Symbol not found or delisted"}
            else:
                return {"success": False, "error": f"API error: {response.status_code}"}

        except requests.RequestException as e:
            return {"success": False, "error": f"Request failed: {type(e).__name__}"}
        except Exception as e:
            LOGGER.exception(f"Error fetching OHLCV for {symbol}: {e}")
            return {"success": False, "error": f"{type(e).__name__}: {str(e)}"}

    def _update_metadata(self, db: Session, symbol: str, days: int) -> None:
        from db.models import OhlcvMetadata

        metadata = (
            db.query(OhlcvMetadata)
            .filter(OhlcvMetadata.symbol == symbol)
            .first()
        )

        if metadata:
            metadata.last_fetched_at = datetime.now(timezone.utc)
            metadata.days_stored = days
        else:
            metadata = OhlcvMetadata(
                symbol=symbol,
                last_fetched_at=datetime.now(timezone.utc),
                days_stored=days,
            )
            db.add(metadata)

        db.commit()

    def _cleanup_old_data(self, db: Session, symbol: str, window_start: date) -> None:
        from db.models import OhlcvDaily

        deleted = (
            db.query(OhlcvDaily)
            .filter(
                and_(
                    OhlcvDaily.symbol == symbol,
                    OhlcvDaily.trade_date < window_start,
                )
            )
            .delete()
        )

        if deleted > 0:
            db.commit()
            LOGGER.debug(f"[{symbol}] Deleted {deleted} old candles")

    def purge_all(self) -> Dict[str, Any]:
        from db.database import SessionLocal
        from db.models import OhlcvDaily, OhlcvMetadata

        db = SessionLocal()
        try:
            candle_count = db.query(OhlcvDaily).count()
            metadata_count = db.query(OhlcvMetadata).count()

            db.query(OhlcvDaily).delete()
            db.query(OhlcvMetadata).delete()
            db.commit()

            LOGGER.info(f"Purged {candle_count} candles and {metadata_count} metadata entries")
            return {
                "operation": "ohlcv_purge_all",
                "candles_deleted": candle_count,
                "metadata_deleted": metadata_count,
            }
        except Exception as e:
            db.rollback()
            LOGGER.error(f"Error purging OHLCV data: {e}")
            return {"operation": "ohlcv_purge_all", "error": str(e)}
        finally:
            db.close()

    def purge_for_symbols(self, symbols: List[str]) -> Dict[str, Any]:
        from db.database import SessionLocal
        from db.models import OhlcvDaily, OhlcvMetadata

        db = SessionLocal()
        try:
            candle_count = 0
            metadata_count = 0

            for symbol in symbols:
                sym_upper = symbol.upper()
                candle_count += db.query(OhlcvDaily).filter(OhlcvDaily.symbol == sym_upper).delete()
                metadata_count += db.query(OhlcvMetadata).filter(OhlcvMetadata.symbol == sym_upper).delete()

            db.commit()

            LOGGER.info(f"Purged {candle_count} candles and {metadata_count} metadata for {len(symbols)} symbols")
            return {
                "operation": "ohlcv_purge_symbols",
                "symbols_purged": len(symbols),
                "candles_deleted": candle_count,
                "metadata_deleted": metadata_count,
            }
        except Exception as e:
            db.rollback()
            LOGGER.error(f"Error purging OHLCV data: {e}")
            return {"operation": "ohlcv_purge_symbols", "error": str(e)}
        finally:
            db.close()

    def get_existing_symbols(self) -> List[str]:
        from db.database import SessionLocal
        from db.models import OhlcvMetadata, OhlcvDaily

        db = SessionLocal()
        try:
            # Get symbols that have actual candle data in ohlcv_daily
            symbols_with_candles = set(
                r[0] for r in db.query(OhlcvDaily.symbol).distinct().all()
            )
            
            # Also include symbols from metadata that might have failed before
            all_metadata = [s[0] for s in db.query(OhlcvMetadata.symbol).all()]
            
            # Combine both - prefer symbols with actual candle data
            result = list(symbols_with_candles.union(set(all_metadata)))
            return result
        finally:
            db.close()

    def inspect_symbol(self, symbol: str, days: int = 100) -> Dict[str, Any]:
        from db.database import SessionLocal
        from db.models import OhlcvDaily
        from datetime import timedelta

        sym_upper = symbol.upper()
        db = SessionLocal()
        try:
            cutoff = date.today() - timedelta(days=days)

            candles = (
                db.query(OhlcvDaily)
                .filter(
                    OhlcvDaily.symbol == sym_upper,
                    OhlcvDaily.trade_date >= cutoff,
                )
                .order_by(OhlcvDaily.trade_date.desc())
                .limit(days)
                .all()
            )

            if not candles:
                return {
                    "symbol": sym_upper,
                    "date_from": None,
                    "date_to": None,
                    "candles": [],
                    "error": "No data found for this symbol",
                }

            dates = [c.trade_date for c in candles]
            return {
                "symbol": sym_upper,
                "date_from": min(dates).isoformat() if dates else None,
                "date_to": max(dates).isoformat() if dates else None,
                "candles": [
                    {
                        "date": c.trade_date.isoformat(),
                        "open": c.open,
                        "high": c.high,
                        "low": c.low,
                        "close": c.close,
                        "volume": c.volume,
                    }
                    for c in candles
                ],
            }
        except Exception as e:
            LOGGER.error(f"Error inspecting OHLCV for {symbol}: {e}")
            return {"symbol": sym_upper, "error": str(e)}
        finally:
            db.close()
