"""Trades repository for persisting normalized trade data."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from db.database import SessionLocal
from db.models import UserTrade

LOGGER = logging.getLogger("tradecraftx.trades")


class TradesRepository:
    def __init__(self, db: Session):
        self._db = db

    def upsert_trades(self, trades: List[Dict]) -> int:
        count = 0
        for trade in trades:
            existing = (
                self._db.query(UserTrade)
                .filter(
                    and_(
                        UserTrade.user_id == trade.get("user_id"),
                        UserTrade.broker == trade.get("broker"),
                        UserTrade.trade_id == trade.get("trade_id"),
                    )
                )
                .first()
            )

            if existing:
                for key, value in trade.items():
                    if key != "id":
                        setattr(existing, key, value)
            else:
                self._db.add(UserTrade(**trade))
            count += 1
        self._db.commit()
        return count

    def get_trades_for_user(
        self,
        user_id: int,
        broker: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        symbols: Optional[List[str]] = None,
    ) -> List[Dict]:
        query = self._db.query(UserTrade).filter(
            UserTrade.user_id == user_id,
            UserTrade.broker == broker,
        )

        if from_date:
            query = query.filter(UserTrade.trade_date >= from_date)
        if to_date:
            query = query.filter(UserTrade.trade_date <= to_date)
        if symbols:
            query = query.filter(UserTrade.symbol.in_(symbols))

        return [
            {
                "symbol": t.symbol,
                "isin": t.isin,
                "trade_date": t.trade_date,
                "exchange": t.exchange,
                "segment": t.segment,
                "series": t.series,
                "side": t.side,
                "quantity": t.quantity,
                "price": t.price,
                "trade_id": t.trade_id,
                "order_id": t.order_id,
                "order_execution_time": t.order_execution_time,
            }
            for t in query.all()
        ]

    def get_trade_count(
        self,
        user_id: int,
        broker: str,
        from_date: Optional[str] = None,
    ) -> int:
        query = self._db.query(func.count(UserTrade.id)).filter(
            UserTrade.user_id == user_id,
            UserTrade.broker == broker,
        )
        if from_date:
            query = query.filter(UserTrade.trade_date >= from_date)
        return query.scalar() or 0

    def get_latest_trade_date(self, user_id: int, broker: str) -> Optional[str]:
        result = (
            self._db.query(func.max(UserTrade.trade_date))
            .filter(
                UserTrade.user_id == user_id,
                UserTrade.broker == broker,
            )
            .scalar()
        )
        return result

    def get_symbols_with_trades(self, user_id: int, broker: str) -> List[str]:
        results = (
            self._db.query(UserTrade.symbol)
            .filter(UserTrade.user_id == user_id, UserTrade.broker == broker)
            .distinct()
            .all()
        )
        return [r[0] for r in results]


def get_repository() -> TradesRepository:
    db = SessionLocal()
    return TradesRepository(db)
