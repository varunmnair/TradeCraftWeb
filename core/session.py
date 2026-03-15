# core/session.py

import time
from datetime import datetime
import json
import os
import logging
from core.cmp import CMPManager
from core.utils import read_csv


class SessionCache:
    GTT_PLAN_CACHE_PATH = "data/gtt_plan_cache.json"

    def __init__(self, session_manager, market_data_connection_id: int = None, ttl: int = 300, tenant_id: int = None, user_id: int = None):
        self.ttl = ttl
        self.last_refreshed = 0
        self.broker = None # Will be set from main_menu
        self.session_manager = session_manager # Store the session manager
        self.market_data_connection_id = market_data_connection_id  # Upstox connection for market data
        self.holdings = []
        self.entry_levels = []
        self.gtt_symbols = set()
        self.cmp_manager = None # Initialize lazily
        self.gtt_cache = []
        self.tenant_id = tenant_id
        self.user_id = user_id

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

        #print("🔄 Refreshing all caches...")
        self.refresh_holdings()
        self.refresh_entry_levels()
        self.refresh_gtt_cache()
        self.refresh_cmp_cache()
        self.last_refreshed = time.time()

    def refresh_holdings(self):
        self.holdings = self.broker.get_holdings()

    def refresh_entry_levels(self):
        # First try to load from DB if tenant_id and user_id are available
        logging.info(f"refresh_entry_levels: tenant_id={self.tenant_id}, user_id={self.user_id}")
        db_entry_levels = self._load_from_db()
        if db_entry_levels:
            logging.info(f"Loaded {len(db_entry_levels)} entry levels from DB")
            self.entry_levels = db_entry_levels
            return
        
        # Fall back to CSV
        csv_path = f"data/{self.broker.user_id}-{self.broker.broker_name}-entry-levels.csv"
        logging.info(f"Falling back to CSV: {csv_path}")
        self.entry_levels = self.broker.load_entry_levels(csv_path)

    def _load_from_db(self):
        """Load entry levels from DB if available."""
        if not self.tenant_id or not self.user_id:
            logging.info("tenant_id or user_id not available, skipping DB load")
            return None
        
        if not self.broker:
            logging.info("broker not available, skipping DB load")
            return None
        
        broker_name = getattr(self.broker, 'broker_name', None) or getattr(self.broker, 'broker', None)
        broker_user_id = getattr(self.broker, 'user_id', None)
        
        if not broker_name or not broker_user_id:
            logging.info("broker_name or broker_user_id not available, skipping DB load")
            return None
        
        try:
            from core.services.entry_strategy_service import get_entry_strategy_service
            service = get_entry_strategy_service()
            levels = service.get_entry_levels_for_user(
                self.tenant_id, 
                self.user_id, 
                broker=broker_name,
                broker_user_id=broker_user_id
            )
            logging.info(f"DB returned {len(levels)} entry levels for tenant={self.tenant_id}, user={self.user_id}, broker={broker_name}")
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

    def get_historical_data(self, symbol: str, exchange: str, interval: str, to_date=None, from_date=None):
        """
        Delegates the historical data fetch call to the broker.
        """
        if self.is_stale():
            self.refresh_all_caches()
        return self.cmp_manager.get_historical_data(symbol, exchange, interval, to_date, from_date)

    # ──────────────── GTT Plan Cache ──────────────── #
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
