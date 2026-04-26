"""Session data management framework for unified data loading/storing/purging."""

from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from db.database import SessionLocal
from db.models import SessionHolding, UserTrade, EntryStrategy, EntryLevel

if TYPE_CHECKING:
    from core.runtime.session_registry import SessionContext

logger = logging.getLogger("tradecraftx.session_data")


class SessionDataManager:
    """
    Unified manager for session-scoped data (holdings, order history, entry strategies).
    
    Data flow:
    - First page visit: Fetch from broker → Store in DB
    - Subsequent visits: Load from DB (fast)
    - Refresh button: Fetch from broker → Store in DB (upsert)
    - Session close: Purge from DB
    """

    def __init__(self, context: "SessionContext"):
        self.context = context

    @property
    def user_id(self) -> Optional[int]:
        return getattr(self.context, 'user_record_id', None)

    @property
    def session_id(self) -> Optional[str]:
        return getattr(self.context, 'session_id', None)

    @property
    def broker_name(self) -> Optional[str]:
        return getattr(self.context, 'broker_name', None)

    @property
    def broker_user_id(self) -> Optional[str]:
        return getattr(self.context, 'broker_user_id', None)

    def has_broker(self) -> bool:
        return getattr(self.context, 'broker', None) is not None

    def get_broker(self):
        return getattr(self.context, 'broker', None)

    def get_session_cache(self):
        return getattr(self.context, 'session_cache', None)

    # ==================== Holdings ====================

    def load_holdings(self) -> List[Dict[str, Any]]:
        """Load holdings from DB. Returns empty list if none found."""
        if not self.session_id:
            return []
        
        db = SessionLocal()
        try:
            holdings = db.query(SessionHolding).filter(
                SessionHolding.session_id == self.session_id
            ).all()
            
            return [
                {
                    "symbol": h.symbol,
                    "exchange": h.exchange,
                    "quantity": h.quantity,
                    "average_price": h.average_price,
                    "last_price": h.last_price,
                    "invested": h.invested,
                    "pnl": h.pnl,
                    "pnl_pct": h.pnl_pct,
                    "quality": h.quality,
                    "isin": h.isin,
                    "fetched_at": h.fetched_at.isoformat() if h.fetched_at else None,
                }
                for h in holdings
            ]
        finally:
            db.close()

    def store_holdings(self, holdings: List[Dict[str, Any]]) -> int:
        """Store holdings to DB (upsert). Returns count of stored holdings."""
        if not self.session_id or not self.user_id:
            return 0
        
        db = SessionLocal()
        try:
            db.query(SessionHolding).filter(
                SessionHolding.session_id == self.session_id
            ).delete()
            
            for h in holdings:
                db.add(SessionHolding(
                    user_id=self.user_id,
                    session_id=self.session_id,
                    symbol=h.get("symbol", "").upper(),
                    exchange=h.get("exchange", "NSE"),
                    quantity=h.get("quantity", 0),
                    average_price=h.get("average_price", 0.0),
                    last_price=h.get("last_price"),
                    invested=h.get("invested"),
                    pnl=h.get("pnl"),
                    pnl_pct=h.get("pnl_pct"),
                    quality=h.get("quality"),
                    isin=h.get("isin"),
                ))
            
            db.commit()
            logger.info(f"Stored {len(holdings)} holdings for session {self.session_id}")
            return len(holdings)
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to store holdings: {e}")
            raise
        finally:
            db.close()

    def fetch_holdings(self) -> List[Dict[str, Any]]:
        """Fetch holdings from broker. Returns raw broker response."""
        if not self.has_broker():
            return []
        return self.get_broker().get_holdings() or []

    def refresh_holdings(self) -> List[Dict[str, Any]]:
        """Fetch from broker and store in DB. Returns refreshed holdings."""
        holdings = self.fetch_holdings()
        if holdings:
            self.store_holdings(holdings)
            cache = self.get_session_cache()
            if cache:
                cache.holdings = holdings
        return holdings

    def load_or_refresh_holdings(self) -> List[Dict[str, Any]]:
        """Load from DB if available, otherwise fetch from broker."""
        cached = self.load_holdings()
        if cached:
            cache = self.get_session_cache()
            if cache:
                cache.holdings = cached
            return cached
        return self.refresh_holdings()

    def purge_holdings(self) -> int:
        """Delete holdings from DB for this session."""
        if not self.session_id:
            return 0
        
        db = SessionLocal()
        try:
            count = db.query(SessionHolding).filter(
                SessionHolding.session_id == self.session_id
            ).delete()
            db.commit()
            logger.info(f"Purged {count} holdings for session {self.session_id}")
            return count
        finally:
            db.close()

    # ==================== Order History ====================

    def load_order_history(self) -> List[Dict[str, Any]]:
        """Load order history from DB."""
        if not self.session_id:
            return []
        
        db = SessionLocal()
        try:
            trades = db.query(UserTrade).filter(
                UserTrade.session_id == self.session_id
            ).all()
            
            result = [
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
                    "source": t.source,
                }
                for t in trades
            ]
            
            if result:
                source = result[0].get("source", "unknown")
                cache = self.get_session_cache()
                if cache:
                    cache.set_order_history(result, source=source)
            
            return result
        finally:
            db.close()

    def store_order_history(self, trades: List[Dict[str, Any]], source: str) -> int:
        """Store order history to DB (upsert)."""
        if not self.session_id or not self.user_id:
            return 0
        
        db = SessionLocal()
        try:
            db.query(UserTrade).filter(
                UserTrade.session_id == self.session_id
            ).delete()
            
            for trade in trades:
                db.add(UserTrade(
                    user_id=self.user_id,
                    session_id=self.session_id,
                    broker=self.broker_name,
                    symbol=trade.get("symbol", ""),
                    isin=trade.get("isin"),
                    trade_date=trade.get("trade_date", ""),
                    exchange=trade.get("exchange", ""),
                    segment=trade.get("segment", ""),
                    series=trade.get("series", ""),
                    side=trade.get("side", ""),
                    quantity=trade.get("quantity", 0),
                    price=trade.get("price", 0),
                    trade_id=trade.get("trade_id"),
                    order_id=trade.get("order_id"),
                    order_execution_time=trade.get("order_execution_time"),
                    source=source,
                ))
            
            db.commit()
            logger.info(f"Stored {len(trades)} trades for session {self.session_id}")
            return len(trades)
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to store order history: {e}")
            raise
        finally:
            db.close()

    def fetch_order_history(self) -> tuple[List[Dict[str, Any]], str]:
        """Fetch order history from broker. Returns (trades, source)."""
        if not self.has_broker():
            return [], "none"
        
        broker = self.get_broker()
        if self.broker_name == "upstox":
            orders = broker.trades() or []
            trades = []
            for order in orders:
                fill_ts = order.get("fill_timestamp")
                if isinstance(fill_ts, datetime):
                    trade_date = fill_ts.strftime("%Y-%m-%d")
                elif isinstance(fill_ts, str):
                    try:
                        trade_date = datetime.strptime(fill_ts[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
                    except ValueError:
                        trade_date = None
                else:
                    trade_date = None
                
                trades.append({
                    "symbol": order.get("tradingsymbol", "").replace("-EQ", "").strip().upper(),
                    "isin": order.get("isin"),
                    "trade_date": trade_date,
                    "exchange": order.get("exchange", "NSE"),
                    "segment": "EQ",
                    "series": "EQ",
                    "side": "BUY" if order.get("transaction_type") == "BUY" else "SELL",
                    "quantity": order.get("quantity", 0),
                    "price": order.get("average_price", 0),
                    "trade_id": order.get("trade_id"),
                    "order_id": order.get("order_id"),
                    "order_execution_time": trade_date,
                    "source": "upstox_api",
                })
            return trades, "upstox_api"
        
        elif self.broker_name == "zerodha":
            orders = broker.trades() or []
            trades = []
            for order in orders:
                trades.append({
                    "symbol": order.get("symbol", "").upper(),
                    "isin": order.get("isin"),
                    "trade_date": order.get("trade_date", ""),
                    "exchange": order.get("exchange", "NSE"),
                    "segment": order.get("segment", "EQ"),
                    "series": order.get("series", "EQ"),
                    "side": order.get("side", "").upper(),
                    "quantity": order.get("quantity", 0),
                    "price": order.get("price", 0),
                    "trade_id": order.get("trade_id"),
                    "order_id": order.get("order_id"),
                    "order_execution_time": order.get("order_execution_time"),
                    "source": "zerodha_api",
                })
            return trades, "zerodha_api"
        
        return [], "none"

    def refresh_order_history(self) -> tuple[List[Dict[str, Any]], str]:
        """Fetch from broker and store in DB. Returns (trades, source)."""
        trades, source = self.fetch_order_history()
        if trades:
            self.store_order_history(trades, source)
            cache = self.get_session_cache()
            if cache:
                cache.set_order_history(trades, source=source)
        return trades, source

    def purge_order_history(self) -> int:
        """Delete order history from DB for this session."""
        if not self.session_id:
            return 0
        
        db = SessionLocal()
        try:
            count = db.query(UserTrade).filter(
                UserTrade.session_id == self.session_id
            ).delete()
            db.commit()
            logger.info(f"Purged {count} trades for session {self.session_id}")
            return count
        finally:
            db.close()

    # ==================== Entry Strategies ====================

    def load_entry_strategies(self) -> List[Dict[str, Any]]:
        """Load entry strategies from DB."""
        if not self.user_id:
            return []
        
        db = SessionLocal()
        try:
            strategies = db.query(EntryStrategy).filter(
                EntryStrategy.user_id == self.user_id,
                EntryStrategy.broker == self.broker_name,
            )
            if self.broker_user_id:
                strategies = strategies.filter(EntryStrategy.broker_user_id == self.broker_user_id)
            
            strategies = strategies.all()
            
            result = []
            for s in strategies:
                levels = db.query(EntryLevel).filter(
                    EntryLevel.strategy_id == s.id
                ).order_by(EntryLevel.level_no).all()
                
                result.append({
                    "id": s.id,
                    "symbol": s.symbol,
                    "exchange": s.exchange,
                    "allocated": s.allocated,
                    "quality": s.quality,
                    "dynamic_averaging_enabled": s.dynamic_averaging_enabled,
                    "averaging_rules": self._parse_json(s.averaging_rules_json),
                    "levels": [
                        {
                            "level_no": l.level_no,
                            "price": l.price,
                            "is_active": l.is_active,
                        }
                        for l in levels
                    ],
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                })
            
            cache = self.get_session_cache()
            if cache:
                cache.entry_levels = result
            
            return result
        finally:
            db.close()

    def store_entry_strategies(self, strategies: List[Dict[str, Any]]) -> int:
        """Store entry strategies to DB (upsert)."""
        if not self.user_id:
            return 0
        
        db = SessionLocal()
        try:
            existing = db.query(EntryStrategy).filter(
                EntryStrategy.user_id == self.user_id,
                EntryStrategy.broker == self.broker_name,
            )
            if self.broker_user_id:
                existing = existing.filter(EntryStrategy.broker_user_id == self.broker_user_id)
            
            existing_strategies = existing.all()
            existing_ids = [s.id for s in existing_strategies]
            
            if existing_ids:
                db.query(EntryLevel).filter(
                    EntryLevel.strategy_id.in_(existing_ids)
                ).delete(synchronize_session=False)
                db.query(EntryStrategy).filter(
                    EntryStrategy.id.in_(existing_ids)
                ).delete(synchronize_session=False)
            
            for strat in strategies:
                strategy = EntryStrategy(
                    user_id=self.user_id,
                    symbol=strat.get("symbol", "").upper(),
                    exchange=strat.get("exchange", "NSE"),
                    broker=self.broker_name,
                    broker_user_id=self.broker_user_id,
                    allocated=strat.get("allocated"),
                    quality=strat.get("quality"),
                    dynamic_averaging_enabled=strat.get("dynamic_averaging_enabled", False),
                    averaging_rules_json=json.dumps(strat.get("averaging_rules", {})) if strat.get("averaging_rules") else None,
                )
                db.add(strategy)
                db.flush()
                
                for level in strat.get("levels", []):
                    db.add(EntryLevel(
                        strategy_id=strategy.id,
                        level_no=level.get("level_no", 1),
                        price=level.get("price", 0),
                        is_active=level.get("is_active", True),
                    ))
            
            db.commit()
            logger.info(f"Stored {len(strategies)} entry strategies for session {self.session_id}")
            return len(strategies)
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to store entry strategies: {e}")
            raise
        finally:
            db.close()

    def export_strategies_csv(self) -> str:
        """Export entry strategies to CSV format."""
        strategies = self.load_entry_strategies()
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            "symbol", "exchange", "allocated", "quality", "dynamic_averaging",
            "level_1_price", "level_1_active", "level_2_price", "level_2_active",
            "level_3_price", "level_3_active", "level_4_price", "level_4_active",
            "level_5_price", "level_5_active",
        ])
        
        for s in strategies:
            levels = s.get("levels", [])
            row = [
                s.get("symbol", ""),
                s.get("exchange", "NSE"),
                s.get("allocated", ""),
                s.get("quality", ""),
                "Y" if s.get("dynamic_averaging_enabled") else "N",
            ]
            
            for i in range(1, 6):
                level = next((l for l in levels if l.get("level_no") == i), None)
                if level:
                    row.append(level.get("price", ""))
                    row.append("Y" if level.get("is_active", True) else "N")
                else:
                    row.extend(["", ""])
            
            writer.writerow(row)
        
        return output.getvalue()

    def purge_entry_strategies(self) -> int:
        """Delete entry strategies from DB for this session scope."""
        if not self.user_id:
            return 0
        
        db = SessionLocal()
        try:
            strategies = db.query(EntryStrategy).filter(
                EntryStrategy.user_id == self.user_id,
                EntryStrategy.broker == self.broker_name,
            )
            if self.broker_user_id:
                strategies = strategies.filter(EntryStrategy.broker_user_id == self.broker_user_id)
            
            strategies = strategies.all()
            count = len(strategies)
            
            if strategies:
                strategy_ids = [s.id for s in strategies]
                db.query(EntryLevel).filter(
                    EntryLevel.strategy_id.in_(strategy_ids)
                ).delete(synchronize_session=False)
                db.query(EntryStrategy).filter(
                    EntryStrategy.id.in_(strategy_ids)
                ).delete(synchronize_session=False)
                db.commit()
            
            logger.info(f"Purged {count} entry strategies for session {self.session_id}")
            return count
        finally:
            db.close()

    # ==================== Bulk Operations ====================

    def purge_all(self) -> Dict[str, int]:
        """Purge all session data from DB. Returns counts of purged records."""
        return {
            "holdings": self.purge_holdings(),
            "order_history": self.purge_order_history(),
            "entry_strategies": self.purge_entry_strategies(),
        }

    def load_all(self) -> Dict[str, Any]:
        """Load all session data from DB."""
        return {
            "holdings": self.load_holdings(),
            "order_history": self.load_order_history(),
            "entry_strategies": self.load_entry_strategies(),
        }

    @staticmethod
    def _parse_json(value: Optional[str]) -> Optional[Dict]:
        """Parse JSON string to dict."""
        if not value:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None
