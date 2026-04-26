import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from db.database import SessionLocal
from db.models import EntryStrategy, UserTrade


MAX_HISTORY_DAYS = 400


class HoldingsAnalyzer:
    def __init__(self, user_id: str, broker_name: str, user_record_id: Optional[int] = None):
        self.user_id = user_id
        self.broker_name = broker_name
        self.user_record_id = user_record_id

    def _get_quality_map(self) -> Dict[str, str]:
        """Get quality ratings from EntryStrategy database table."""
        if not self.user_record_id:
            logging.debug("No user_record_id, cannot load quality from DB")
            return {}

        db = SessionLocal()
        try:
            strategies = db.query(EntryStrategy).filter(
                EntryStrategy.user_id == self.user_record_id,
                EntryStrategy.broker == self.broker_name,
            ).all()

            return {s.symbol.upper(): (s.quality or "-") for s in strategies}
        except Exception as e:
            logging.warning(f"Failed to load quality from DB: {e}")
            return {}
        finally:
            db.close()

    def _get_trades_from_db(self) -> List[Dict]:
        """Load trades from user_trades table for Age/ROI calculations."""
        if not self.user_record_id:
            logging.debug("No user_record_id, cannot load trades from DB")
            return []

        db = SessionLocal()
        try:
            logging.info(f"Loading trades from DB: user_record_id={self.user_record_id}, broker_name={self.broker_name}")
            
            trades = db.query(UserTrade).filter(
                UserTrade.user_id == self.user_record_id,
                UserTrade.broker == self.broker_name,
            ).all()

            logging.info(f"Found {len(trades)} trades in DB for user_record_id={self.user_record_id}")

            result = []
            for t in trades:
                trade_date = None
                if t.trade_date:
                    try:
                        trade_date = datetime.strptime(t.trade_date, "%Y-%m-%d").date()
                    except (ValueError, TypeError):
                        pass

                result.append({
                    "symbol": t.symbol.upper(),
                    "side": t.side.upper() if t.side else "BUY",
                    "quantity": t.quantity or 0,
                    "price": t.price or 0,
                    "trade_date": trade_date,
                })

            return result
        except Exception as e:
            logging.warning(f"Failed to load trades from DB: {e}")
            return []
        finally:
            db.close()

    def apply_filters(self, results: List[Dict], filters: Dict) -> List[Dict]:
        if not filters:
            return results
        filtered = []
        for r in results:
            match = True
            for key, val in filters.items():
                if key not in r:
                    match = False
                    break
                if isinstance(val, (int, float)):
                    if r[key] < val:
                        match = False
                        break
                elif isinstance(val, str):
                    if str(r[key]).lower() != val.lower():
                        match = False
                        break
            if match:
                filtered.append(r)
        return filtered

    def get_total_invested(self, holdings: List[Dict]) -> float:
        return sum(
            h["quantity"] * h["average_price"]
            for h in holdings
            if h["quantity"] > 0 and h["average_price"] > 0
        )

    def analyze_holdings(
        self, broker, cmp_manager, filters=None, sort_by="weighted_roi"
    ) -> List[Dict]:
        logging.debug("Analyzing holdings...")
        if filters is None:
            filters = {}

        quality_map = self._get_quality_map()
        if not quality_map:
            logging.info("No entry strategies found in DB. Quality will be N/A.")

        trades = self._get_trades_from_db()
        has_trades = len(trades) > 0
        if not has_trades:
            logging.info("No order history found in DB. Age/ROI will be N/A.")

        # Group trades by symbol
        trades_by_symbol: Dict[str, List[Dict]] = {}
        if has_trades:
            for trade in trades:
                symbol = trade["symbol"]
                if symbol not in trades_by_symbol:
                    trades_by_symbol[symbol] = []
                trades_by_symbol[symbol].append(trade)

        holdings = broker.get_holdings()
        logging.debug(f"Found {len(holdings)} holdings.")
        results = []
        total_invested = self.get_total_invested(holdings)

        for holding in holdings:
            symbol = holding["tradingsymbol"]
            symbol_clean = symbol.replace("#", "").replace("-BE", "").upper()
            quantity = holding["quantity"] + holding.get("t1_quantity", 0)
            avg_price = holding["average_price"]
            invested = quantity * avg_price

            ltp = holding["last_price"]
            if not ltp:
                ltp = cmp_manager.get_cmp(holding.get("exchange", "NSE"), symbol)
            if not ltp:
                logging.warning(f"LTP not found for {symbol}. Skipping.")
                continue

            current_value = quantity * ltp
            pnl = current_value - invested
            pnl_pct = (pnl / invested * 100) if invested else 0

            quality = quality_map.get(symbol_clean, None)

            # Calculate Age/ROI from trade history
            days_held = None
            roi_per_day = None
            profit_per_day = None
            weighted_roi = None
            age_reason = None

            if has_trades and symbol_clean in trades_by_symbol:
                symbol_trades = trades_by_symbol[symbol_clean]
                symbol_trades = [t for t in symbol_trades if t["trade_date"] is not None]
                symbol_trades.sort(key=lambda x: x["trade_date"], reverse=True)

                # Find oldest BUY trade for this symbol
                buy_trades = [t for t in symbol_trades if t.get("side", "").upper() == "BUY"]
                
                if not buy_trades:
                    age_reason = "no_buy_trades"
                else:
                    # Check if oldest BUY is beyond MAX_HISTORY_DAYS
                    oldest_buy_date = min(t["trade_date"] for t in buy_trades)
                    today = datetime.today().date()
                    days_from_oldest_buy = (today - oldest_buy_date).days
                    
                    if days_from_oldest_buy > MAX_HISTORY_DAYS:
                        # Cap age at MAX_HISTORY_DAYS
                        days_held = MAX_HISTORY_DAYS
                        age_reason = "buy_trades_beyond_400_days"
                        roi_per_day = (pnl_pct / days_held) if days_held > 0 else 0
                        profit_per_day = (pnl / days_held) if days_held > 0 else 0
                        weighted_roi = (
                            (roi_per_day * invested / total_invested) if total_invested > 0 else 0
                        )
                    else:
                        # Normal age calculation using weighted average
                        qty_needed = quantity
                        weighted_sum = 0
                        total_qty = 0

                        for trade in symbol_trades:
                            if qty_needed <= 0:
                                break
                            used_qty = min(qty_needed, trade["quantity"])
                            weighted_sum += used_qty * trade["trade_date"].toordinal()
                            total_qty += used_qty
                            qty_needed -= used_qty

                        if total_qty > 0:
                            avg_date_ordinal = weighted_sum / total_qty
                            avg_date = datetime.fromordinal(int(avg_date_ordinal)).date()
                            days_held = (today - avg_date).days
                            roi_per_day = (pnl_pct / days_held) if days_held > 0 else 0
                            profit_per_day = (pnl / days_held) if days_held > 0 else 0
                            weighted_roi = (
                                (roi_per_day * invested / total_invested) if total_invested > 0 else 0
                            )
                        else:
                            age_reason = "no_buy_trades"
            elif not has_trades:
                age_reason = "order_history_not_fetched"
            else:
                age_reason = "no_trades_for_symbol"

            # Trend - placeholder for now (logic to be added later)
            trend = "NA"

            results.append(
                {
                    "symbol": symbol,
                    "exchange": holding.get("exchange", "NSE"),
                    "quantity": quantity,
                    "average_price": avg_price,
                    "last_price": ltp,
                    "invested": round(invested, 2),
                    "profit": round(pnl, 2),
                    "profit_pct": round(pnl_pct, 2),
                    "quality": quality,
                    "age": days_held,
                    "age_reason": age_reason,
                    "roi_per_day": round(roi_per_day, 4) if roi_per_day is not None else None,
                    "profit_per_day": round(profit_per_day, 2) if profit_per_day is not None else None,
                    "weighted_roi": round(weighted_roi, 4) if weighted_roi is not None else None,
                    "trend": trend,
                }
            )

        logging.debug(f"Generated {len(results)} results before filtering.")
        results = self.apply_filters(results, filters)
        logging.debug(f"Found {len(results)} results after applying filters.")

        sorted_results = sorted(
            results,
            key=lambda x: x.get(sort_by, float('-inf')) if x.get(sort_by) is not None else float('-inf'),
            reverse=True
        )
        logging.debug(f"Sorted results by {sort_by}.")

        return sorted_results
