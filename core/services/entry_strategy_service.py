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
        self, tenant_id: int, user_id: int, broker: str = None, broker_user_id: str = None
    ) -> list[dict[str, Any]]:
        query = self.db.query(EntryStrategy).filter(
            EntryStrategy.tenant_id == tenant_id,
            EntryStrategy.user_id == user_id,
        )
        
        # Filter by broker scope if provided
        if broker:
            query = query.filter(EntryStrategy.broker == broker)
        if broker_user_id:
            query = query.filter(EntryStrategy.broker_user_id == broker_user_id)
        
        strategies = query.all()

        result = []
        for strategy in strategies:
            levels = (
                self.db.query(EntryLevel)
                .filter(
                    EntryLevel.strategy_id == strategy.id,
                    EntryLevel.is_active == True,
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

    def get_cmp_for_symbol(
        self, symbol: str, tenant_id: int | None, user_id: int | None
    ) -> dict[str, Any] | None:
        return None


_entry_strategy_service: EntryStrategyService | None = None


def get_entry_strategy_service() -> EntryStrategyService:
    global _entry_strategy_service
    if _entry_strategy_service is None:
        _entry_strategy_service = EntryStrategyService()
    return _entry_strategy_service
