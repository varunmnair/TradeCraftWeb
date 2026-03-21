"""Trades service for managing user trades and readiness checks."""

from __future__ import annotations

import csv
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from core.services.market_data_repository import (
    MarketDataRepository,
)
from core.services.market_data_repository import (
    get_repository as get_market_repo,
)
from core.services.trades_repository import TradesRepository, get_repository

LOGGER = logging.getLogger("tradecraftx.trades_service")


class TradesService:
    def __init__(
        self,
        repo: Optional[TradesRepository] = None,
        market_repo: Optional[MarketDataRepository] = None,
    ):
        self._repo = repo or get_repository()
        self._market_repo = market_repo or get_market_repo()

    def get_readiness(
        self,
        user_id: int,
        broker: str,
        holdings_symbols: List[str],
    ) -> Dict:
        market_data_ready = True
        trades_ready = True
        blocking_reason: Optional[str] = None

        missing_cmp = []
        missing_candles = []
        missing_trades = []

        if holdings_symbols:
            quotes = self._market_repo.get_quotes_for_symbols(holdings_symbols)
            for sym in holdings_symbols:
                quote = quotes.get(sym)
                if not quote or quote.get("cmp") is None:
                    missing_cmp.append(sym)

            candles = self._market_repo.get_candles_for_symbols(
                holdings_symbols, days=200
            )
            for sym in holdings_symbols:
                if not candles.get(sym) or len(candles.get(sym, [])) < 200:
                    missing_candles.append(sym)

        from_date = (date.today() - timedelta(days=400)).strftime("%Y-%m-%d")
        trade_count = self._repo.get_trade_count(user_id, broker, from_date)

        if trade_count == 0:
            trades_ready = False
            missing_trades = holdings_symbols
            if broker == "upstox":
                blocking_reason = "TRADES_SYNC_REQUIRED"
            else:
                blocking_reason = "TRADEBOOK_NOT_UPLOADED"

        if missing_cmp or missing_candles:
            market_data_ready = False
            if not blocking_reason:
                blocking_reason = "MARKET_DATA_MISSING"

        ready_to_analyze = market_data_ready and trades_ready

        return {
            "broker": broker,
            "market_data_ready": market_data_ready,
            "trades_ready": trades_ready,
            "ready_to_analyze": ready_to_analyze,
            "blocking_reason": blocking_reason,
            "missing": {
                "cmp": missing_cmp,
                "candles": missing_candles,
                "trades": missing_trades,
            },
        }

    def sync_upstox_trades(
        self,
        user_id: int,
        broker,
        days: int = 400,
    ) -> Dict:
        orders = broker.get_orders() or []
        trades = broker.get_trades() or []

        normalized = []
        seen = set()

        for order in orders:
            trade_id = str(order.get("order_id") or "")
            if not trade_id or trade_id in seen:
                continue
            seen.add(trade_id)

            order_time = order.get("order_timestamp") or order.get("created_at") or ""
            if isinstance(order_time, datetime):
                order_time = order_time.isoformat()

            normalized.append(
                {
                    "user_id": user_id,
                    "broker": "upstox",
                    "symbol": order.get("tradingsymbol", ""),
                    "isin": order.get("isin", ""),
                    "trade_date": str(order_time)[:10] if order_time else "",
                    "exchange": order.get("exchange", ""),
                    "segment": "EQ",
                    "series": "EQ",
                    "side": order.get("transaction_type", "").upper(),
                    "quantity": int(order.get("quantity", 0) or 0),
                    "price": float(order.get("price", 0) or 0),
                    "trade_id": trade_id,
                    "order_id": str(order.get("order_id", "")),
                    "order_execution_time": str(order_time),
                    "source": "upstox_api",
                }
            )

        for trade in trades:
            trade_id = str(trade.get("trade_id") or "")
            if not trade_id or trade_id in seen:
                continue
            seen.add(trade_id)

            exec_time = (
                trade.get("order_execution_time") or trade.get("trade_timestamp") or ""
            )
            if isinstance(exec_time, datetime):
                exec_time = exec_time.isoformat()

            normalized.append(
                {
                    "user_id": user_id,
                    "broker": "upstox",
                    "symbol": trade.get("symbol", "") or trade.get("tradingsymbol", ""),
                    "isin": trade.get("isin", ""),
                    "trade_date": str(exec_time)[:10] if exec_time else "",
                    "exchange": trade.get("exchange", ""),
                    "segment": "EQ",
                    "series": "EQ",
                    "side": (
                        trade.get("trade_type", "").upper()
                        if trade.get("trade_type")
                        else "BUY"
                    ),
                    "quantity": int(trade.get("quantity", 0) or 0),
                    "price": float(
                        trade.get("price", 0) or trade.get("average_price", 0) or 0
                    ),
                    "trade_id": trade_id,
                    "order_id": str(trade.get("order_id", "")),
                    "order_execution_time": str(exec_time),
                    "source": "upstox_api",
                }
            )

        count = self._repo.upsert_trades(normalized)
        symbols_covered = len(set(t["symbol"] for t in normalized if t["symbol"]))

        return {
            "rows_ingested": count,
            "symbols_covered": symbols_covered,
            "errors": [],
        }

    def upload_zerodha_tradebook(
        self,
        user_id: int,
        file_content: str,
    ) -> Dict:
        lines = file_content.strip().split("\n")
        if not lines:
            return {"rows_ingested": 0, "symbols_covered": 0, "errors": ["Empty file"]}

        reader = csv.DictReader(lines)
        headers = reader.fieldnames or []
        expected_headers = {
            "symbol",
            "isin",
            "trade_date",
            "exchange",
            "segment",
            "series",
            "trade_type",
            "auction",
            "quantity",
            "price",
            "trade_id",
            "order_id",
            "order_execution_time",
        }
        actual_headers = {h.strip().lower() for h in headers}
        if not expected_headers.issubset(actual_headers):
            missing = expected_headers - actual_headers
            return {
                "rows_ingested": 0,
                "symbols_covered": 0,
                "errors": [f"Missing columns: {missing}"],
            }

        normalized = []
        errors = []
        seen = set()

        for i, row in enumerate(reader, start=2):
            try:
                trade_id = str(row.get("trade_id", "")).strip()
                if not trade_id:
                    errors.append(f"Row {i}: missing trade_id")
                    continue

                key = (user_id, "zerodha", trade_id)
                if key in seen:
                    continue
                seen.add(key)

                normalized.append(
                    {
                        "user_id": user_id,
                        "broker": "zerodha",
                        "symbol": str(row.get("symbol", "")).strip().upper(),
                        "isin": str(row.get("isin", "")).strip() or None,
                        "trade_date": str(row.get("trade_date", "")).strip(),
                        "exchange": str(row.get("exchange", "")).strip().upper(),
                        "segment": str(row.get("segment", "")).strip().upper() or "EQ",
                        "series": str(row.get("series", "")).strip().upper() or "EQ",
                        "side": (
                            "BUY"
                            if str(row.get("trade_type", "")).upper() == "BUY"
                            else "SELL"
                        ),
                        "quantity": int(float(row.get("quantity", 0) or 0)),
                        "price": float(row.get("price", 0) or 0),
                        "trade_id": trade_id,
                        "order_id": str(row.get("order_id", "")).strip() or None,
                        "order_execution_time": str(
                            row.get("order_execution_time", "")
                        ).strip()
                        or None,
                        "source": "zerodha_upload",
                    }
                )
            except Exception as e:
                errors.append(f"Row {i}: {str(e)}")

        if not normalized:
            return {
                "rows_ingested": 0,
                "symbols_covered": 0,
                "errors": errors if errors else ["No valid rows"],
            }

        count = self._repo.upsert_trades(normalized)
        symbols_covered = len(set(t["symbol"] for t in normalized))

        return {
            "rows_ingested": count,
            "symbols_covered": symbols_covered,
            "errors": errors[:10],
        }

    def get_trades_for_symbols(
        self,
        user_id: int,
        broker: str,
        symbols: List[str],
    ) -> List[Dict]:
        from_date = (date.today() - timedelta(days=400)).strftime("%Y-%m-%d")
        return self._repo.get_trades_for_user(
            user_id, broker, from_date, symbols=symbols
        )


def get_trades_service() -> TradesService:
    return TradesService()
