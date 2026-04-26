# core/session.py

import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Optional

from core.cmp import CMPManager


class SessionCache:
    GTT_PLAN_CACHE_PATH = "data/gtt_plan_cache.json"

    def __init__(
        self,
        session_manager,
        market_data_connection_id: int = None,
        ttl: int = 300,
        user_id: int = None,
        session_id: str = None,
    ):
        self.ttl = ttl
        self.last_refreshed = 0
        self.broker = None
        self.session_manager = session_manager
        self.market_data_connection_id = market_data_connection_id
        self.holdings = []
        self.entry_levels = []
        self.gtt_symbols = set()
        self.cmp_manager = None
        self.gtt_cache = []
        self.user_id = user_id
        self.session_id = session_id
        
        # Order history management (session-scoped)
        self._order_history: Dict[str, List[Dict]] = {}  # symbol -> list of trades
        self._order_history_fetched_at: Optional[datetime] = None
        self._order_history_source: Optional[str] = None  # "upstox_api" or "zerodha_csv"

    def set_order_history(self, trades: List[Dict], source: str):
        """Store order history for this session, grouped by symbol."""
        self._order_history = {}
        for trade in trades:
            symbol = trade.get("symbol", "").strip().upper()
            if symbol:
                if symbol not in self._order_history:
                    self._order_history[symbol] = []
                self._order_history[symbol].append(trade)
        self._order_history_fetched_at = datetime.now()
        self._order_history_source = source
        
        # Calculate trade count
        total_trades = sum(len(t) for t in self._order_history.values())
        logging.info(f"Stored {total_trades} trades for {len(self._order_history)} symbols")
        
        # Log symbols
        symbols = list(self._order_history.keys())[:5]
        logging.debug(f"Symbols (first 5): {symbols}")

    def get_order_history(self, symbol: Optional[str] = None) -> Optional[List[Dict]]:
        """Get order history, optionally filtered by symbol."""
        if symbol:
            return self._order_history.get(symbol.strip().upper(), [])
        return self._order_history

    def get_order_history_status(self) -> Dict:
        """Get the current status of order history for this session."""
        all_dates = []
        for trades in self._order_history.values():
            for trade in trades:
                if trade.get("trade_date"):
                    all_dates.append(trade["trade_date"])
        
        date_from = min(all_dates) if all_dates else None
        date_to = max(all_dates) if all_dates else None
        
        return {
            "available": bool(self._order_history),
            "trade_count": sum(len(trades) for trades in self._order_history.values()),
            "symbol_count": len(self._order_history),
            "fetched_at": self._order_history_fetched_at,
            "source": self._order_history_source,
            "date_from": date_from,
            "date_to": date_to,
        }

    def clear_order_history(self):
        """Clear order history for this session."""
        self._order_history = {}
        self._order_history_fetched_at = None
        self._order_history_source = None
        logging.info("Cleared order history for session")

    def get_holdings_enriched(self) -> List[Dict]:
        """
        Get holdings enriched with order history data.
        Uses broker CMP if available, otherwise marks as None.
        """
        holdings = self.get_holdings()
        enriched = []
        
        for h in holdings:
            symbol = h.get("symbol") or h.get("tradingsymbol", "")
            symbol = symbol.strip().upper()
            
            enriched_h = {
                "symbol": symbol,
                "exchange": h.get("exchange", "NSE"),
                "quantity": h.get("quantity", 0),
                "average_price": h.get("average_price", 0),
                "last_price": h.get("last_price"),  # May be None if not from broker
                "invested": h.get("quantity", 0) * h.get("average_price", 0),
            }
            
            # Calculate P&L if last_price is available
            if enriched_h["last_price"] is not None:
                enriched_h["pnl"] = (enriched_h["last_price"] - enriched_h["average_price"]) * enriched_h["quantity"]
                if enriched_h["average_price"] > 0:
                    enriched_h["pnl_pct"] = ((enriched_h["last_price"] - enriched_h["average_price"]) / enriched_h["average_price"]) * 100
                else:
                    enriched_h["pnl_pct"] = None
            else:
                enriched_h["pnl"] = None
                enriched_h["pnl_pct"] = None
            
            # Add order history data if available
            trades = self._order_history.get(symbol, [])
            if trades:
                buy_trades = [t for t in trades if t.get("side", "").upper() == "BUY"]
                sell_trades = [t for t in trades if t.get("side", "").upper() == "SELL"]
                
                total_buy_qty = sum(t.get("quantity", 0) for t in buy_trades)
                total_sell_qty = sum(t.get("quantity", 0) for t in sell_trades)
                total_buy_value = sum(t.get("quantity", 0) * t.get("price", 0) for t in buy_trades)
                total_sell_value = sum(t.get("quantity", 0) * t.get("price", 0) for t in sell_trades)
                
                enriched_h["avg_buy_price"] = total_buy_value / total_buy_qty if total_buy_qty > 0 else None
                enriched_h["total_buy_qty"] = total_buy_qty
                enriched_h["avg_sell_price"] = total_sell_value / total_sell_qty if total_sell_qty > 0 else None
                enriched_h["total_sell_qty"] = total_sell_qty
                enriched_h["buy_value"] = total_buy_value
                enriched_h["sell_value"] = total_sell_value
                enriched_h["net_value"] = total_buy_value - total_sell_value
                
                # Parse dates
                dates = []
                for t in buy_trades:
                    d = t.get("trade_date")
                    if isinstance(d, str):
                        dates.append(d)
                    elif isinstance(d, datetime):
                        dates.append(d.strftime("%Y-%m-%d"))
                
                if dates:
                    dates.sort()
                    enriched_h["first_buy_date"] = dates[0] if dates else None
                    enriched_h["last_buy_date"] = dates[-1] if dates else None
            else:
                # Order history not available
                enriched_h["avg_buy_price"] = None
                enriched_h["total_buy_qty"] = None
                enriched_h["avg_sell_price"] = None
                enriched_h["total_sell_qty"] = None
                enriched_h["buy_value"] = None
                enriched_h["sell_value"] = None
                enriched_h["net_value"] = None
                enriched_h["first_buy_date"] = None
                enriched_h["last_buy_date"] = None
            
            # ROI/Trend fields (empty for now)
            enriched_h["trend"] = None
            enriched_h["trend_days"] = None
            enriched_h["trend_roi"] = None
            
            enriched.append(enriched_h)
        
        return enriched

    def is_stale(self) -> bool:
        return (time.time() - self.last_refreshed) > self.ttl

    def refresh_all_caches(self):
        if not self.broker:
            print("Broker not initialized. Please login first.")
            return

        if not self.cmp_manager:
            self.cmp_manager = CMPManager(
                csv_path="data/Name-symbol-mapping.csv",
                broker=self.broker,
                session_manager=self.session_manager,
                market_data_connection_id=self.market_data_connection_id,
                ttl=self.ttl,
            )

        self.refresh_holdings()
        self.refresh_entry_levels()
        self.refresh_gtt_cache()
        self.refresh_cmp_cache()
        self.last_refreshed = time.time()

    def refresh_holdings(self):
        self.holdings = self.broker.get_holdings()
        self._trigger_ohlcv_refresh()

    def _trigger_ohlcv_refresh(self):
        symbols = set()
        for h in self.holdings:
            sym = h.get("symbol") or h.get("tradingsymbol")
            if sym:
                symbols.add(str(sym).strip().upper())

        if not symbols:
            return

        from api.dependencies import get_job_runner, JOB_OHLCV_REFRESH_SYMBOLS

        session_id = self.session_id or f"holdings-{self.user_id or 'unknown'}"

        try:
            job_runner = get_job_runner()
            job_runner.start_job(
                session_id=session_id,
                job_type=JOB_OHLCV_REFRESH_SYMBOLS,
                payload={"symbols": list(symbols)},
            )
            logging.info(f"Triggered OHLCV refresh for {len(symbols)} symbols")
        except Exception as e:
            logging.warning(f"Failed to trigger OHLCV refresh: {e}")

    def refresh_entry_levels(self):
        logging.info(f"refresh_entry_levels: user_id={self.user_id}")

        db_entry_levels = self._load_from_db()
        if db_entry_levels:
            logging.info(f"Loaded {len(db_entry_levels)} entry levels from DB")
            self.entry_levels = db_entry_levels
        else:
            logging.info("No entry levels found in DB")
            self.entry_levels = []

    def _load_from_db(self):
        """Load entry levels from DB if available."""
        if not self.user_id:
            logging.info("user_id not available, skipping DB load")
            return None

        if not self.broker:
            logging.info("broker not available, skipping DB load")
            return None

        broker_name = getattr(self.broker, "broker_name", None) or getattr(
            self.broker, "broker", None
        )
        broker_user_id = getattr(self.broker, "broker_user_id", None)

        logging.info(
            f"_load_from_db: broker_name={broker_name}, broker_user_id={broker_user_id}, user_id={self.user_id}"
        )

        if broker_user_id is None:
            logging.warning(
                "_load_from_db: broker_user_id is None, will match strategies with broker_user_id IS NULL or any value"
            )

        if not broker_name or not broker_user_id:
            logging.info(
                "broker_name or broker_user_id not available, skipping DB load"
            )
            return None

        try:
            from core.services.entry_strategy_service import get_entry_strategy_service

            service = get_entry_strategy_service()
            levels = service.get_entry_levels_for_user(
                self.user_id, broker=broker_name, broker_user_id=broker_user_id
            )
            logging.info(
                f"DB returned {len(levels)} entry levels for user={self.user_id}, broker={broker_name}, broker_user_id={broker_user_id}"
            )

            from db.database import SessionLocal
            from db.models import EntryStrategy

            db = SessionLocal()
            try:
                total_in_db = (
                    db.query(EntryStrategy)
                    .filter(
                        EntryStrategy.user_id == self.user_id,
                        EntryStrategy.broker == broker_name,
                    )
                    .count()
                )
                logging.info(
                    f"DEBUG: Total EntryStrategy in DB for broker={broker_name}: {total_in_db}"
                )

                if total_in_db > 0 and len(levels) == 0:
                    strategies = (
                        db.query(EntryStrategy)
                        .filter(
                            EntryStrategy.user_id == self.user_id,
                            EntryStrategy.broker == broker_name,
                        )
                        .all()
                    )
                    logging.info(
                        f"DEBUG: First strategy broker_user_id: {strategies[0].broker_user_id if strategies else 'none'}"
                    )
            finally:
                db.close()

            return levels
        except Exception as e:
            logging.warning(f"Failed to load entry levels from DB: {e}")
            return None

    def refresh_gtt_cache(self):
        try:
            self.gtt_cache = self.broker.get_gtt_orders()
        except Exception as e:
            print(f"❌ Failed to refresh GTT cache: {e}")
            self.gtt_cache = []

    def refresh_cmp_cache(self):
        self.cmp_manager.refresh_cache(self.holdings, self.gtt_cache, self.entry_levels)

    def get_gtt_cache(self):
        if self.is_stale():
            self.refresh_all_caches()
        return self.gtt_cache

    def get_existing_gtt_symbols(self):
        if self.is_stale():
            self.refresh_all_caches()
        return {
            g.tradingsymbol.strip().upper()
            for g in self.gtt_cache
            if g.transaction_type == self.broker.TRANSACTION_TYPE_BUY
        }

    def get_holdings(self):
        if self.is_stale():
            self.refresh_all_caches()
        return self.holdings

    def get_entry_levels(self):
        if self.is_stale():
            self.refresh_all_caches()
        return self.entry_levels

    def get_cmp_manager(self):
        if self.is_stale():
            self.refresh_all_caches()
        return self.cmp_manager

    def get_historical_data(
        self, symbol: str, exchange: str, interval: str, to_date=None, from_date=None
    ):
        """Delegates the historical data fetch call to the broker."""
        if self.is_stale():
            self.refresh_all_caches()
        return self.cmp_manager.get_historical_data(
            symbol, exchange, interval, to_date, from_date
        )

    def write_gtt_plan(self, orders: list):
        os.makedirs(os.path.dirname(self.GTT_PLAN_CACHE_PATH), exist_ok=True)
        try:
            with open(self.GTT_PLAN_CACHE_PATH, "w") as f:
                json.dump(orders, f, indent=2)
        except Exception as e:
            logging.error(f"❌ Failed to write GTT plan cache: {e}")

    def read_gtt_plan(self) -> list:
        if not os.path.exists(self.GTT_PLAN_CACHE_PATH):
            return []
        try:
            logging.debug("📂 Reading GTT plan from cache: ")
            with open(self.GTT_PLAN_CACHE_PATH, "r") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"❌ Failed to read GTT plan cache: {e}")
            return []

    def delete_gtt_plan(self):
        try:
            os.remove(self.GTT_PLAN_CACHE_PATH)
        except Exception as e:
            logging.warning(f"⚠️ Failed to delete GTT plan cache: {e}")
