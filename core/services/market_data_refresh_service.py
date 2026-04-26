"""Market data refresh service for fetching from Upstox."""

from __future__ import annotations

import logging
import os
import time
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from core.services.market_data_repository import MarketDataRepository, get_repository
from core.services.symbol_catalog_service import SymbolCatalogService
from core.session_manager import SessionManager

LOGGER = logging.getLogger("tradecraftx.market_data_refresh")


class MarketDataRefreshService:
    BATCH_SIZE = 50

    def __init__(self, repo: Optional[MarketDataRepository] = None):
        self._repo = repo or get_repository()
        self._isin_cache: Dict[str, str] = {}
        self._token: Optional[str] = None
        self._symbol_catalog_service = SymbolCatalogService()

    def _load_isin_cache(self) -> None:
        """Load ISIN map from symbol catalog."""
        self._isin_cache = self._symbol_catalog_service.get_symbol_isin_map()
        LOGGER.info(f"Loaded {len(self._isin_cache)} ISINs from symbol catalog")

    def _get_instrument_key(self, symbol: str) -> Optional[str]:
        symbol_clean = symbol.replace("-BE", "").strip().upper()
        isin = self._isin_cache.get(symbol_clean)
        if isin:
            return f"NSE_EQ|{isin}"
        return None

    def get_status(self) -> Dict[str, Any]:
        catalog_status = self._symbol_catalog_service.get_status()
        symbol_count = catalog_status["total_symbols"]

        self._repo.get_quotes_for_symbols([], None)  # Ensure cached
        with self._repo._db as db:
            from sqlalchemy import func

            from db.models import MarketQuoteDaily

            cmp_row = (
                db.query(func.max(MarketQuoteDaily.as_of_ts))
                .filter(MarketQuoteDaily.cmp.isnot(None))
                .scalar()
            )
            cmp_as_of_ts = cmp_row.isoformat() if cmp_row else None

            quote_date = (
                db.query(func.max(MarketQuoteDaily.trade_date))
                .filter(MarketQuoteDaily.cmp.isnot(None))
                .scalar()
            )
            cmp_trade_date = quote_date if quote_date else None

        all_symbols = self._symbol_catalog_service.get_all_symbols()
        if all_symbols:
            quotes = self._repo.get_quotes_for_symbols(all_symbols)

            def is_missing(s):
                q = quotes.get(s)
                return q is None or q.get("cmp") is None

            cmp_missing = sum(1 for s in all_symbols if is_missing(s))

            candles = self._repo.get_candles_for_symbols(all_symbols, days=400)
            candles_missing = sum(
                1 for s in all_symbols if len(candles.get(s) or []) == 0
            )
        else:
            cmp_missing = 0
            candles_missing = 0

        return {
            "symbol_catalog_count": symbol_count,
            "last_refresh_ts": cmp_as_of_ts,
            "cmp_trade_date": cmp_trade_date,
            "cmp_as_of_ts": cmp_as_of_ts,
            "coverage": {
                "cmp_missing_count": cmp_missing,
                "candles_missing_count": candles_missing,
            },
        }

    def refresh(
        self,
        session_manager: SessionManager,
        connection_id: int,
    ) -> Dict[str, Any]:
        LOGGER.info("=== Starting market data refresh ===")
        self._load_isin_cache()
        LOGGER.info(f"ISIN cache loaded: {len(self._isin_cache)} entries")

        self._token = os.environ.get("UPSTOX_ANALYTICS_TOKEN")
        if not self._token:
            LOGGER.error("UPSTOX_ANALYTICS_TOKEN not configured")
            return {"error": "UPSTOX_ANALYTICS_TOKEN_NOT_CONFIGURED"}
        LOGGER.info(f"Using analytics token (length: {len(self._token)})")

        symbols = self._symbol_catalog_service.get_all_symbols()
        if not symbols:
            return {
                "total": 0,
                "processed": 0,
                "success": 0,
                "failed": 0,
                "missing": [],
                "errors": {},
            }

        quotes = self._repo.get_quotes_for_symbols(symbols)
        self._repo.get_candles_for_symbols(symbols, days=400)  # Ensure candles cached
        last_candle_dates = self._repo._get_last_candle_dates(symbols)

        today_str = date.today().strftime("%Y-%m-%d")
        today = date.today()

        needs_cmp = []
        needs_candles = {}
        MIN_DAYS_TO_FETCH = 5

        for symbol in symbols:
            quote = quotes.get(symbol)
            as_of_ts = quote.get("as_of_ts", "") if quote else ""
            quote_date = as_of_ts[:10] if as_of_ts else None

            if not quote_date or quote_date != today_str:
                needs_cmp.append(symbol)

            last_date = last_candle_dates.get(symbol)
            if last_date:
                from_date = last_date + timedelta(days=1)
                if from_date <= today:
                    days_diff = (today - from_date).days
                    if days_diff < MIN_DAYS_TO_FETCH:
                        from_date = today - timedelta(days=MIN_DAYS_TO_FETCH)
                    needs_candles[symbol] = from_date
            else:
                needs_candles[symbol] = today - timedelta(days=100)

        LOGGER.info(
            f"Need CMP for {len(needs_cmp)} symbols, candles for {len(needs_candles)} symbols"
        )
        LOGGER.info(
            f"Processing in batches of {self.BATCH_SIZE}: candles (1 API call/symbol), quotes (bulk API)"
        )
        LOGGER.info(f"Candles needed for symbols: {list(needs_candles.keys())[:10]}...")

        # Log a sample curl command for debugging - copy this to test manually
        if needs_candles:
            sample_symbol = list(needs_candles.keys())[0]
            sample_from = needs_candles[sample_symbol]
            sample_key = self._get_instrument_key(sample_symbol)
            if sample_key:
                sample_url = f"https://api.upstox.com/v2/historical-candle/{sample_key}/day/{today.strftime('%Y-%m-%d')}/{sample_from.strftime('%Y-%m-%d')}"
                token_preview = (
                    f"{self._token[:10]}...{self._token[-5:]}"
                    if self._token and len(self._token) > 20
                    else self._token
                )
                LOGGER.info(
                    "============================================================"
                )
                LOGGER.info("DEBUG CURL - copy and run this to test the API manually:")
                LOGGER.info(
                    f'curl -H "Authorization: Bearer {self._token}" -H "Accept: application/json" "{sample_url}"'
                )
                LOGGER.info(f"(Token preview: {token_preview})")
                LOGGER.info(
                    "============================================================"
                )

        total = len(symbols)
        success = 0
        failed = 0
        errors: Dict[str, str] = {}

        candles_count = len(needs_candles)
        LOGGER.info(f"=== Starting candle fetch for {candles_count} symbols ===")
        for i in range(0, candles_count, self.BATCH_SIZE):
            batch = list(needs_candles.keys())[i : i + self.BATCH_SIZE]
            self._fetch_candles_batch(batch, needs_candles, today)

            LOGGER.info(
                f"Candles: {min(i + self.BATCH_SIZE, candles_count)}/{candles_count} processed"
            )
            time.sleep(0.3)

        quotes_count = len(needs_cmp)
        for i in range(0, quotes_count, self.BATCH_SIZE):
            batch = needs_cmp[i : i + self.BATCH_SIZE]
            self._fetch_quotes_batch(batch, today_str)

            LOGGER.info(
                f"CMP quotes: {min(i + self.BATCH_SIZE, quotes_count)}/{quotes_count} (bulk API)"
            )
            time.sleep(0.3)

        success = len(needs_cmp) + len(needs_candles)
        LOGGER.info(
            f"=== Refresh complete: CMP={len(needs_cmp)}, Candles={len(needs_candles)}, Total={total} ==="
        )
        return {
            "total": total,
            "processed": success,
            "success": success,
            "failed": failed,
            "missing": [],
            "errors": errors,
            "cmp_fetched": len(needs_cmp),
            "candles_fetched": len(needs_candles),
        }

    def _fetch_candles_batch(
        self,
        symbols: List[str],
        date_map: Dict[str, date],
        to_date: date,
    ) -> None:
        import requests

        LOGGER.info(
            f"[_fetch_candles_batch] Processing {len(symbols)} symbols: {symbols[:5]}..."
        )
        for symbol in symbols:
            instrument_key = self._get_instrument_key(symbol)
            if not instrument_key:
                LOGGER.warning(f"Could not resolve instrument key for {symbol}")
                continue

            from_date = date_map.get(symbol)
            if not from_date:
                continue

            if from_date >= to_date:
                LOGGER.warning(
                    f"[{symbol}] from_date ({from_date}) >= to_date ({to_date}), skipping"
                )
                continue

            url = f"https://api.upstox.com/v2/historical-candle/{instrument_key}/day/{to_date.strftime('%Y-%m-%d')}/{from_date.strftime('%Y-%m-%d')}"
            LOGGER.info(f"[{symbol}] API URL: {url}")
            headers = {
                "Accept": "application/json",
                "Authorization": f"Bearer {self._token}",
            }

            try:
                response = requests.get(url, headers=headers, timeout=30)
                if response.status_code == 200:
                    data = response.json()

                    # Check API status first
                    api_status = data.get("status")
                    if api_status != "success":
                        LOGGER.warning(
                            f"[{symbol}] API error: status={api_status}, response={data}"
                        )
                        continue

                    candle_data_resp = data.get("data", {})
                    raw_candles = (
                        candle_data_resp.get("candles", [])
                        if isinstance(candle_data_resp, dict)
                        else []
                    )

                    if not raw_candles:
                        LOGGER.warning(f"[{symbol}] No candles in API response: {data}")
                        continue

                    candle_data = self._transform_candles(symbol, raw_candles)
                    LOGGER.info(
                        f"[{symbol}] Raw candles count: {len(raw_candles)}, Transformed: {len(candle_data) if candle_data else 0}"
                    )
                    if candle_data and len(candle_data) > 0:
                        LOGGER.info(f"[{symbol}] First candle: {candle_data[0]}")
                        LOGGER.info(f"[{symbol}] Last candle: {candle_data[-1]}")
                        LOGGER.info(
                            f"[{symbol}] Calling upsert_candles with {len(candle_data)} candles..."
                        )
                        saved = self._repo.upsert_candles(
                            {symbol: candle_data}, source="upstox"
                        )
                        LOGGER.info(f"[{symbol}] upsert_candles returned: {saved}")
                    else:
                        LOGGER.warning(
                            f"[{symbol}] No candle data after transformation"
                        )
                        if raw_candles:
                            LOGGER.warning(
                                f"[{symbol}] First raw candle: {raw_candles[0]}"
                            )
                elif response.status_code == 400:
                    try:
                        err_data = response.json()
                        error_msg = str(err_data)
                    except Exception:
                        error_msg = (
                            response.text[:200] if response.text else "Unknown error"
                        )
                    LOGGER.warning(f"400 for {symbol} ({instrument_key}): {error_msg}")
                elif response.status_code == 404:
                    LOGGER.warning(
                        f"404 for {symbol} ({instrument_key}): Symbol not found or delisted"
                    )
                else:
                    LOGGER.warning(
                        f"Failed to fetch candles for {symbol} ({instrument_key}): {response.status_code}"
                    )
            except Exception as e:
                LOGGER.error(f"Error fetching candles for {symbol}: {e}")

    def _fetch_quotes_batch(self, symbols: List[str], trade_date: str) -> None:
        import requests

        instrument_keys = []
        symbol_map: Dict[str, str] = {}

        for symbol in symbols:
            instrument_key = self._get_instrument_key(symbol)
            if instrument_key:
                instrument_keys.append(instrument_key)
                symbol_map[instrument_key] = symbol

        if not instrument_keys:
            return

        url = f"https://api.upstox.com/v3/market-quote/ltp?instrument_key={','.join(instrument_keys)}"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token}",
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                quotes_data = data.get("data", {})
                quotes = {}
                for key, quote in quotes_data.items():
                    symbol = symbol_map.get(key)
                    if symbol:
                        cmp_price = quote.get("last_price")
                        if cmp_price:
                            quotes[symbol] = float(cmp_price)

                if quotes:
                    self._repo.upsert_quotes(quotes, trade_date, source="upstox")
            else:
                LOGGER.warning(f"Failed to fetch quotes batch: {response.status_code}")
        except Exception as e:
            LOGGER.error(f"Error fetching quotes batch: {e}")

    def _transform_candles(self, symbol: str, candles: List[Any]) -> List[Dict]:
        result = []
        for c in candles:
            if len(c) >= 5:
                result.append(
                    {
                        "trade_date": str(c[0])[:10],
                        "open": float(c[1]) if c[1] else None,
                        "high": float(c[2]) if c[2] else None,
                        "low": float(c[3]) if c[3] else None,
                        "close": float(c[4]) if c[4] else None,
                        "volume": int(c[5]) if len(c) > 5 and c[5] else None,
                    }
                )
        return result


def get_market_data_refresh_service() -> MarketDataRefreshService:
    return MarketDataRefreshService()
