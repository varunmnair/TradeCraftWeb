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
        if self._db is not None:
            return self._db
        return SessionLocal()

    def _fresh_session(self) -> Session:
        if self._db is not None:
            return self._db
        return SessionLocal()

    def get_entry_levels_for_user(
        self,
        user_id: int,
        broker: str = None,
        broker_user_id: str = None,
        connection_broker_user_id: str = None,
    ) -> list[dict[str, Any]]:
        db = self._fresh_session()
        owns_session = self._db is None
        try:
            query = db.query(EntryStrategy).filter(
                EntryStrategy.user_id == user_id,
            )

            if broker:
                query = query.filter(EntryStrategy.broker == broker)
            if broker_user_id:
                from sqlalchemy import or_

                filters = [EntryStrategy.broker_user_id == broker_user_id]
                if connection_broker_user_id and connection_broker_user_id != broker_user_id:
                    filters.append(EntryStrategy.broker_user_id == connection_broker_user_id)
                filters.append(EntryStrategy.broker_user_id.is_(None))
                query = query.filter(or_(*filters))

            strategies = query.all()

            result = []
            for strategy in strategies:
                levels = (
                    db.query(EntryLevel)
                    .filter(
                        EntryLevel.strategy_id == strategy.id,
                        EntryLevel.is_active.is_(True),
                    )
                    .order_by(EntryLevel.level_no)
                    .all()
                )

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

                entry["da_status"] = strategy.da_status
                entry["da_eligible"] = strategy.da_eligible
                entry["da_confidence_score"] = strategy.da_confidence_score
                entry["thesis_break_price"] = strategy.thesis_break_price
                entry["override_da_enabled"] = strategy.override_da_enabled
                entry["override_da_qty_pct"] = strategy.override_da_qty_pct
                entry["override_sell_offset"] = strategy.override_sell_offset
                entry["override_buyback_price"] = strategy.override_buyback_price
                entry["override_sell_price"] = strategy.override_sell_price

                if levels:
                    for level in levels:
                        if level.level_no == 1:
                            entry["entry1"] = level.price
                        elif level.level_no == 2:
                            entry["entry2"] = level.price
                        elif level.level_no == 3:
                            entry["entry3"] = level.price

                result.append(entry)

            return result
        finally:
            if owns_session:
                db.close()

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
        db = self._fresh_session()
        owns_session = self._db is None
        try:
            query = (
                db.query(EntryStrategy.symbol)
                .filter(
                    EntryStrategy.user_id == user_id,
                )
                .distinct()
            )

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
        finally:
            if owns_session:
                db.close()

    def trigger_ohlcv_refresh_for_user(
        self, user_id: int, broker: str = None, broker_user_id: str = None
    ) -> None:
        symbols = self.get_symbols_for_user(user_id, broker, broker_user_id)
        if symbols:
            from core.market_data.ohlcv_store import ensure_ohlcv

            ensure_ohlcv(symbols)
            logger.info(f"Ensured OHLCV data for {len(symbols)} entry strategy symbols")


_entry_strategy_service: EntryStrategyService | None = None


def get_entry_strategy_service() -> EntryStrategyService:
    global _entry_strategy_service
    if _entry_strategy_service is None:
        _entry_strategy_service = EntryStrategyService()
    return _entry_strategy_service


def _strategy_to_entry_dict(strategy: Any) -> dict[str, Any]:
    """Convert an EntryStrategy ORM object to a plain dict for the DA evaluation service."""
    import json

    d = {
        "symbol": strategy.symbol,
        "dynamic_averaging_enabled": strategy.dynamic_averaging_enabled,
        "thesis_break_price": strategy.thesis_break_price,
        "override_da_enabled": strategy.override_da_enabled,
        "override_da_qty_pct": strategy.override_da_qty_pct,
        "override_sell_offset": strategy.override_sell_offset,
        "override_buyback_price": strategy.override_buyback_price,
        "override_sell_price": strategy.override_sell_price,
        "da_status": strategy.da_status,
        "da_eligible": strategy.da_eligible,
        "da_confidence_score": strategy.da_confidence_score,
    }
    if strategy.averaging_rules_json:
        try:
            rules = json.loads(strategy.averaging_rules_json)
            d["DA Enabled"] = "Y" if strategy.dynamic_averaging_enabled else "N"
            d["DA legs"] = rules.get("legs", 0)
            buyback = rules.get("buyback", [0, 0, 0])
            d["DA E1 Buyback"] = buyback[0] if len(buyback) > 0 else 0
            d["DA E2 Buyback"] = buyback[1] if len(buyback) > 1 else 0
            d["DA E3 Buyback"] = buyback[2] if len(buyback) > 2 else 0
            d["DATriggerOffset"] = rules.get("trigger_offset", 0)
        except (json.JSONDecodeError, TypeError, IndexError):
            pass
    if hasattr(strategy, "levels"):
        try:
            levels = strategy.levels
            for level in levels:
                if level.level_no == 1:
                    d["entry1"] = level.price
                elif level.level_no == 2:
                    d["entry2"] = level.price
                elif level.level_no == 3:
                    d["entry3"] = level.price
        except Exception:
            pass
    return d
