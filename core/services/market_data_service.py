"""Market data service for CMP and candle access."""

from __future__ import annotations

import logging
from datetime import date
from typing import Dict, List, Optional

from core.services.market_data_repository import MarketDataRepository, get_repository
from core.utils import sanitize_for_json

LOGGER = logging.getLogger("tradecraftx.market_data_service")


class MarketDataService:
    def __init__(self, repo: Optional[MarketDataRepository] = None):
        self._repo = repo

    def _get_repo(self) -> MarketDataRepository:
        if self._repo is None:
            self._repo = get_repository()
        return self._repo

    def get_cmp(
        self, symbols: List[str], trade_date: Optional[str] = None
    ) -> Dict[str, any]:
        repo = self._get_repo()
        if trade_date is None:
            trade_date = date.today().strftime("%Y-%m-%d")

        quotes = repo.get_quotes_for_symbols(symbols, trade_date)

        data = {}
        missing = []
        as_of_ts = None

        for sym in symbols:
            quote = quotes.get(sym)
            if quote and quote.get("cmp") is not None:
                data[sym] = quote["cmp"]
                if as_of_ts is None and quote.get("as_of_ts"):
                    as_of_ts = quote["as_of_ts"]
            else:
                missing.append(sym)

        return {
            "trade_date": trade_date,
            "as_of_ts": as_of_ts,
            "data": sanitize_for_json(data),
            "missing": sanitize_for_json(missing),
        }

    def get_candles(self, symbols: List[str], days: int = 400) -> Dict[str, any]:
        from core.market_data.ohlcv_store import OhlcvStoreError, get_ohlcv_multi

        repo = self._get_repo()
        try:
            candles = get_ohlcv_multi(symbols, days=days, db=repo._db)
        except OhlcvStoreError:
            return {
                "data": {},
                "missing_symbols": sanitize_for_json(symbols),
                "error": "OHLCV data not available. Admin may need to run OHLCV refresh from Market Data page.",
            }

        data = {}
        missing_symbols = []

        for sym in symbols:
            candle_list = candles.get(sym, [])
            if candle_list:
                data[sym] = candle_list
            else:
                missing_symbols.append(sym)

        return {
            "data": sanitize_for_json(data),
            "missing_symbols": sanitize_for_json(missing_symbols),
        }

    def get_universe_count(self, universe: str = "NIFTY500") -> int:
        repo = self._get_repo()
        return repo.get_universe_count(universe, enabled_only=True)

    def init_universe_from_csv(
        self, csv_path: str, universe: str = "NIFTY500"
    ) -> Dict[str, any]:
        import csv

        repo = self._get_repo()
        symbols = []
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    sym = row.get("SYMBOL") or row.get("symbol")
                    if sym:
                        symbols.append(str(sym).strip().upper())
        except Exception as e:
            LOGGER.error(f"Failed to read CSV: {e}")
            return {"error": str(e), "count": 0}

        if not symbols:
            return {"error": "No symbols found in CSV", "count": 0}

        count = repo.set_universe_symbols(symbols, universe)
        total = repo.get_universe_count(universe, enabled_only=False)

        return {
            "added": count,
            "total": total,
            "universe": universe,
        }

    def reset_and_init_universe(
        self, csv_path: str, universe: str = "NIFTY500"
    ) -> Dict[str, any]:
        import csv

        repo = self._get_repo()
        symbols = []
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    sym = row.get("SYMBOL") or row.get("symbol")
                    if sym:
                        symbols.append(str(sym).strip().upper())
        except Exception as e:
            LOGGER.error(f"Failed to read CSV: {e}")
            return {"error": str(e), "deleted": 0, "added": 0}

        if not symbols:
            return {"error": "No symbols found in CSV", "deleted": 0, "added": 0}

        deleted = repo.reset_universe_symbols(universe)
        added = repo.set_universe_symbols(symbols, universe)
        total = repo.get_universe_count(universe, enabled_only=False)

        return {
            "deleted": deleted,
            "added": added,
            "total": total,
            "universe": universe,
        }


def get_market_data_service() -> MarketDataService:
    return MarketDataService()
