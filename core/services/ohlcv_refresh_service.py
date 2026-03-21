"""OHLCV refresh service for fetching and storing daily candles."""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from core.session_manager import SessionManager

LOGGER = logging.getLogger("tradecraftx.ohlcv_refresh")

MAX_FAILURES = 100
BATCH_SIZE = 50
SLEEP_BETWEEN_BATCHES = 0.5


class OhlcvRefreshService:
    def __init__(
        self,
        session_manager: Optional[SessionManager] = None,
        connection_id: Optional[int] = None,
    ):
        self._session_manager = session_manager
        self._connection_id = connection_id

    def refresh(
        self,
        session_manager: SessionManager,
        connection_id: int,
        days: int = 200,
    ) -> Dict[str, Any]:
        LOGGER.info(f"=== Starting OHLCV refresh (days={days}) ===")

        from core.services.symbol_catalog_repository import SymbolCatalogRepository
        from db.database import SessionLocal

        db = SessionLocal()
        try:
            repo = SymbolCatalogRepository(db)
            symbols_data = repo.get_all_for_cmp_refresh()
        finally:
            db.close()

        if not symbols_data:
            LOGGER.warning("No symbols in symbol catalog")
            return {
                "operation": "ohlcv_refresh",
                "days": days,
                "total_symbols": 0,
                "processed_symbols": 0,
                "succeeded_symbols": 0,
                "failed_symbols": 0,
                "failure_count": 0,
                "failures": [],
            }

        LOGGER.info(f"Found {len(symbols_data)} symbols in catalog")

        SUPPORTED_SEGMENTS = {"NSE_EQ", "BSE_EQ"}

        symbol_map: Dict[str, Dict[str, str]] = {}
        for item in symbols_data:
            exchange = (item.get("exchange") or "NSE").upper()
            series = (item.get("series") or "EQ").upper()
            segment = f"{exchange}_{series}"
            isin = item.get("isin", "")
            symbol = item.get("symbol", "")
            if isin and segment in SUPPORTED_SEGMENTS:
                symbol_map[symbol] = {
                    "exchange": exchange,
                    "series": series,
                    "segment": segment,
                    "isin": isin,
                    "instrument_key": f"{segment}|{isin}",
                }

        LOGGER.info(f"Built {len(symbol_map)} symbol entries for OHLCV refresh")

        token = session_manager.get_access_token("upstox", connection_id=connection_id)
        if not token:
            LOGGER.error("UPSTOX_NOT_CONNECTED: No access token found")
            return {
                "operation": "ohlcv_refresh",
                "days": days,
                "total_symbols": len(symbol_map),
                "processed_symbols": 0,
                "succeeded_symbols": 0,
                "failed_symbols": len(symbol_map),
                "failure_count": len(symbol_map),
                "failures": [
                    {"symbol": s, "excerpt": "No access token"}
                    for s in list(symbol_map.keys())[:MAX_FAILURES]
                ],
            }

        total_symbols = len(symbol_map)
        processed_symbols = 0
        succeeded_symbols = 0
        failed_symbols = 0
        failures: List[Dict] = []

        today = date.today()
        window_start = today - timedelta(days=days)

        symbols_list = list(symbol_map.keys())

        for i in range(0, len(symbols_list), BATCH_SIZE):
            batch_symbols = symbols_list[i : i + BATCH_SIZE]
            batch_start = i
            batch_end = min(i + BATCH_SIZE, len(symbols_list))
            LOGGER.info(
                f"Processing batch {batch_start + 1}-{batch_end} of {len(symbols_list)}"
            )

            batch_result = self._process_symbol_batch(
                db_session_factory=lambda: SessionLocal(),
                symbols=batch_symbols,
                symbol_map=symbol_map,
                token=token,
                today=today,
                window_start=window_start,
            )

            processed_symbols += batch_result["processed"]
            succeeded_symbols += batch_result["succeeded"]
            failed_symbols += batch_result["failed"]
            failures.extend(batch_result["failures"])

            LOGGER.info(
                f"Batch complete: +{batch_result['succeeded']} succeeded, +{batch_result['failed']} failed"
            )

            if i + BATCH_SIZE < len(symbols_list):
                time.sleep(SLEEP_BETWEEN_BATCHES)

        LOGGER.info(
            f"=== OHLCV refresh complete: {succeeded_symbols}/{total_symbols} succeeded, {failed_symbols} failed ==="
        )

        return {
            "operation": "ohlcv_refresh",
            "days": days,
            "total_symbols": total_symbols,
            "processed_symbols": processed_symbols,
            "succeeded_symbols": succeeded_symbols,
            "failed_symbols": failed_symbols,
            "failure_count": failed_symbols,
            "failures": failures[:MAX_FAILURES],
        }

    def _process_symbol_batch(
        self,
        db_session_factory,
        symbols: List[str],
        symbol_map: Dict[str, Dict[str, str]],
        token: str,
        today: date,
        window_start: date,
    ) -> Dict[str, Any]:
        from db.models import OhlcvDaily

        processed = 0
        succeeded = 0
        failed = 0
        failures: List[Dict] = []

        db = db_session_factory()
        try:
            for symbol in symbols:
                info = symbol_map.get(symbol)
                if not info:
                    failed += 1
                    failures.append({"symbol": symbol, "excerpt": "Not in symbol map"})
                    continue

                max_date = (
                    db.query(func.max(OhlcvDaily.trade_date))
                    .filter(OhlcvDaily.symbol == symbol)
                    .scalar()
                )

                fetch_start = window_start
                if max_date is not None:
                    fetch_start = max(max_date + timedelta(days=1), window_start)

                if fetch_start > today:
                    processed += 1
                    succeeded += 1
                    continue

                result = self._fetch_and_store_ohlcv(
                    db=db,
                    symbol=symbol,
                    instrument_key=info["instrument_key"],
                    token=token,
                    from_date=fetch_start,
                    to_date=today,
                    window_start=window_start,
                )

                processed += 1
                if result["success"]:
                    succeeded += 1
                else:
                    failed += 1
                    failures.append(
                        {
                            "symbol": symbol,
                            "excerpt": result.get("error", "Unknown error"),
                        }
                    )

                time.sleep(0.1)

            db.commit()
        except Exception as e:
            LOGGER.exception(f"Batch error: {e}")
            db.rollback()
            for symbol in symbols:
                if symbol not in [f["symbol"] for f in failures]:
                    failures.append(
                        {
                            "symbol": symbol,
                            "excerpt": f"Batch error: {type(e).__name__}",
                        }
                    )
                    failed += 1
        finally:
            db.close()

        return {
            "processed": processed,
            "succeeded": succeeded,
            "failed": failed,
            "failures": failures[:MAX_FAILURES],
        }

    def _fetch_and_store_ohlcv(
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

        url = f"https://api.upstox.com/v2/historical-candle/{instrument_key}/day/{to_date.strftime('%Y-%m-%d')}/{from_date.strftime('%Y-%m-%d')}"

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
                    return {
                        "success": False,
                        "error": f"API error: {data.get('status')}",
                    }

                candles_raw = data.get("data", {}).get("candles", [])
                if not candles_raw:
                    return {"success": False, "error": "No candles in response"}

                upserted = 0
                for c in candles_raw:
                    if len(c) >= 5:
                        trade_date_str = str(c[0])[:10]
                        try:
                            trade_date = date.fromisoformat(trade_date_str)
                        except ValueError:
                            continue

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
                        upserted += 1

                deleted_count = (
                    db.query(OhlcvDaily)
                    .filter(
                        and_(
                            OhlcvDaily.symbol == symbol,
                            OhlcvDaily.trade_date < window_start,
                        )
                    )
                    .delete()
                )

                LOGGER.debug(
                    f"[{symbol}] Upserted {upserted} candles, deleted {deleted_count} old rows"
                )
                return {"success": True, "upserted": upserted, "deleted": deleted_count}

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
