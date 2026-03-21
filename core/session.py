# core/session.py

import json
import logging
import os
import time

from core.cmp import CMPManager


class SessionCache:
    GTT_PLAN_CACHE_PATH = "data/gtt_plan_cache.json"

    def __init__(
        self,
        session_manager,
        market_data_connection_id: int = None,
        ttl: int = 300,
        user_id: int = None,
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
        self.refresh_entry_levels(force_clear=True)
        self.refresh_gtt_cache()
        self.refresh_cmp_cache()
        self.last_refreshed = time.time()

    def refresh_holdings(self):
        self.holdings = self.broker.get_holdings()

    def refresh_entry_levels(self, force_clear: bool = False):
        logging.info(f"refresh_entry_levels: user_id={self.user_id}")

        if force_clear:
            self._clear_entry_strategies_for_session()

        db_entry_levels = self._load_from_db()
        if db_entry_levels:
            logging.info(f"Loaded {len(db_entry_levels)} entry levels from DB")
            self.entry_levels = db_entry_levels
        else:
            logging.info("No entry levels found in DB")
            self.entry_levels = []

    def _clear_entry_strategies_for_session(self):
        """Clear entry strategies for the current session scope."""
        if not self.user_id:
            return

        broker_name = getattr(self.broker, "broker_name", None) or getattr(
            self.broker, "broker", None
        )
        broker_user_id = getattr(self.broker, "broker_user_id", None)

        if not broker_name:
            return

        try:
            from db.database import SessionLocal
            from db.models import EntryLevel, EntryStrategy

            db = SessionLocal()
            try:
                query = db.query(EntryStrategy).filter(
                    EntryStrategy.user_id == self.user_id,
                    EntryStrategy.broker == broker_name,
                )
                if broker_user_id:
                    query = query.filter(EntryStrategy.broker_user_id == broker_user_id)

                strategies = query.all()

                if strategies:
                    strategy_ids = [s.id for s in strategies]
                    db.query(EntryLevel).filter(
                        EntryLevel.strategy_id.in_(strategy_ids)
                    ).delete(synchronize_session=False)
                    db.query(EntryStrategy).filter(
                        EntryStrategy.id.in_(strategy_ids)
                    ).delete(synchronize_session=False)
                    db.commit()
                    logging.info(
                        f"Cleared {len(strategies)} entry strategies for session scope: broker={broker_name}, broker_user_id={broker_user_id}"
                    )
                else:
                    logging.info(
                        f"No entry strategies to clear for session scope: broker={broker_name}, broker_user_id={broker_user_id}"
                    )
            finally:
                db.close()
        except Exception as e:
            logging.warning(f"Failed to clear entry strategies: {e}")

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
