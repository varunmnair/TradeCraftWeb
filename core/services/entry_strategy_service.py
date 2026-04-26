from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from db.database import SessionLocal
from db.models import EntryLevel, EntryStrategy

logger = logging.getLogger(__name__)


class EntryStrategyService:
    def __init__(self, db: Session | None = None):
        self._db = db

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def get_entry_levels_for_user(
        self, user_id: int, broker: str = None, broker_user_id: str = None
    ) -> list[dict[str, Any]]:
        query = self.db.query(EntryStrategy).filter(
            EntryStrategy.user_id == user_id,
        )

        # Filter by broker scope if provided
        if broker:
            query = query.filter(EntryStrategy.broker == broker)
        if broker_user_id:
            from sqlalchemy import or_

            query = query.filter(
                or_(
                    EntryStrategy.broker_user_id == broker_user_id,
                    EntryStrategy.broker_user_id.is_(None),
                )
            )

        strategies = query.all()

        result = []
        for strategy in strategies:
            levels = (
                self.db.query(EntryLevel)
                .filter(
                    EntryLevel.strategy_id == strategy.id,
                    EntryLevel.is_active.is_(True),
                )
                .order_by(EntryLevel.level_no)
                .all()
            )

            if not levels:
                continue

            entry = {
                "symbol": strategy.symbol,
                "Allocated": strategy.allocated or 0,
                "Quality": strategy.quality or "",
                "exchange": strategy.exchange or "NSE",
                "DA Enabled": "Y" if strategy.dynamic_averaging_enabled else "N",
                "DA legs": 0,
                "DA E1 Buyback": 0,
                "DA E2 Buyback": 0,
                "DA E3 Buyback": 0,
                "DATriggerOffset": 0,
            }

            if strategy.averaging_rules_json:
                try:
                    rules = json.loads(strategy.averaging_rules_json)
                    entry["DA legs"] = rules.get("legs", 0)
                    entry["DA E1 Buyback"] = rules.get("buyback", [0, 0, 0])[0]
                    entry["DA E2 Buyback"] = rules.get("buyback", [0, 0, 0])[1]
                    entry["DA E3 Buyback"] = rules.get("buyback", [0, 0, 0])[2]
                    entry["DATriggerOffset"] = rules.get("trigger_offset", 0)
                except (json.JSONDecodeError, TypeError, IndexError):
                    pass

            for level in levels:
                if level.level_no == 1:
                    entry["entry1"] = level.price
                elif level.level_no == 2:
                    entry["entry2"] = level.price
                elif level.level_no == 3:
                    entry["entry3"] = level.price

            result.append(entry)

        return result

    def get_cmp_for_symbol(self, symbol: str, user_id: int) -> dict[str, Any] | None:
        from api.dependencies import get_global_cmp_manager

        symbol_clean = str(symbol).replace("-BE", "").strip().upper()
        cmp_manager = get_global_cmp_manager()
        price = cmp_manager.get_cmp("NSE", symbol_clean)
        if price is not None:
            return {"symbol": symbol_clean, "last_price": price}
        return None

    def get_symbols_for_user(
        self, user_id: int, broker: str = None, broker_user_id: str = None
    ) -> list[str]:
        query = self.db.query(EntryStrategy.symbol).filter(
            EntryStrategy.user_id == user_id,
        ).distinct()

        if broker:
            query = query.filter(EntryStrategy.broker == broker)
        if broker_user_id:
            from sqlalchemy import or_
            query = query.filter(
                or_(
                    EntryStrategy.broker_user_id == broker_user_id,
                    EntryStrategy.broker_user_id.is_(None),
                )
            )

        return [str(s[0]).upper() for s in query.all() if s[0]]

    def trigger_ohlcv_refresh_for_user(
        self, user_id: int, broker: str = None, broker_user_id: str = None
    ) -> None:
        symbols = self.get_symbols_for_user(user_id, broker, broker_user_id)
        if not symbols:
            return

        from api.dependencies import get_job_runner, JOB_OHLCV_REFRESH_SYMBOLS

        try:
            job_runner = get_job_runner()
            session_id = f"entry-strategy-{user_id}"
            job_runner.start_job(
                session_id=session_id,
                job_type=JOB_OHLCV_REFRESH_SYMBOLS,
                payload={"symbols": symbols},
            )
            logger.info(f"Triggered OHLCV refresh for {len(symbols)} entry strategy symbols")
        except Exception as e:
            logger.warning(f"Failed to trigger OHLCV refresh for entry strategies: {e}")


_entry_strategy_service: EntryStrategyService | None = None


def get_entry_strategy_service() -> EntryStrategyService:
    global _entry_strategy_service
    if _entry_strategy_service is None:
        _entry_strategy_service = EntryStrategyService()
    return _entry_strategy_service
