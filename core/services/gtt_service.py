"""GTT management service wrapper."""

from __future__ import annotations

from typing import Any, Dict, List

from core.gtt_manage import GTTManager
from core.runtime.session_registry import SessionRegistry
from core.utils import sanitize_for_json


class GTTService:
    def __init__(self, registry: SessionRegistry) -> None:
        self._registry = registry

    def analyze_orders(self, session_id: str) -> Dict[str, Any]:
        manager = self._get_manager(session_id)
        orders = manager.analyze_gtt_buy_orders()
        return {"orders": sanitize_for_json(orders)}

    def place_orders(self, session_id: str, plan: List[Dict[str, Any]], *, dry_run: bool = False) -> Dict[str, Any]:
        manager = self._get_manager(session_id)
        results = manager.place_orders(plan, dry_run=dry_run)
        return {"results": sanitize_for_json(results)}

    def adjust_orders(self, session_id: str, orders: List[Dict[str, Any]], target_variance: float) -> Dict[str, Any]:
        manager = self._get_manager(session_id)
        strategy = self._build_strategy(session_id)
        modified = manager.adjust_orders(orders, target_variance, strategy.adjust_trigger_and_order_price)
        return {"orders": sanitize_for_json(modified)}

    def delete_orders(self, session_id: str, symbols: List[str]) -> Dict[str, Any]:
        manager = self._get_manager(session_id)
        deleted = manager.delete_gtts_for_symbols(symbols)
        return {"deleted": sanitize_for_json(deleted)}

    def delete_orders_by_ids(self, session_id: str, gtt_ids: List[str]) -> Dict[str, Any]:
        manager = self._get_manager(session_id)
        deleted = manager.delete_gtts_by_ids(gtt_ids)
        # Convert IDs to strings for API response
        deleted_str = [str(d) for d in deleted]
        return {"deleted": sanitize_for_json(deleted_str), "count": len(deleted_str)}

    def adjust_orders_by_ids(self, session_id: str, gtt_ids: List[str], target_variance: float) -> Dict[str, Any]:
        manager = self._get_manager(session_id)
        strategy = self._build_strategy(session_id)
        
        # Fetch current orders and filter by IDs
        all_orders = manager.analyze_gtt_buy_orders()
        ids_to_adjust = set(str(gid) for gid in gtt_ids)
        orders_to_adjust = [o for o in all_orders if str(o.get("GTT ID")) in ids_to_adjust]
        
        if not orders_to_adjust:
            return {"adjusted": [], "failed": [], "message": "No matching orders found"}
        
        # Track results
        adjusted = []
        failed = []
        
        for order in orders_to_adjust:
            try:
                if order.get("Variance (%)", 0) < target_variance:
                    new_trigger = round(order["LTP"] / (1 + target_variance / 100), 2)
                    new_price, new_trigger = strategy.adjust_trigger_and_order_price(
                        order_price=new_trigger, 
                        ltp=order["LTP"]
                    )
                    
                    # Cancel old and place new
                    manager.broker.cancel_gtt(order["GTT ID"])
                    manager.broker.place_gtt(
                        trigger_type=manager.broker.GTT_TYPE_SINGLE,
                        tradingsymbol=order["Symbol"],
                        exchange=order["Exchange"],
                        trigger_values=[new_trigger],
                        last_price=order["LTP"],
                        orders=[{
                            "transaction_type": manager.broker.TRANSACTION_TYPE_BUY,
                            "quantity": order["Qty"],
                            "order_type": manager.broker.ORDER_TYPE_LIMIT,
                            "product": manager.broker.PRODUCT_CNC,
                            "price": new_price
                        }]
                    )
                    
                    new_variance = round(((order["LTP"] - new_trigger) / new_trigger) * 100, 2)
                    adjusted.append({
                        "GTT ID": order["GTT ID"],
                        "Symbol": order["Symbol"],
                        "old_trigger": order["Trigger Price"],
                        "new_trigger": new_trigger,
                        "old_variance": order["Variance (%)"],
                        "new_variance": new_variance,
                        "status": "adjusted"
                    })
                else:
                    adjusted.append({
                        "GTT ID": order["GTT ID"],
                        "Symbol": order["Symbol"],
                        "status": "skipped",
                        "reason": f"Variance {order['Variance (%)']}% already >= target {target_variance}%"
                    })
            except Exception as e:
                failed.append({
                    "GTT ID": order["GTT ID"],
                    "Symbol": order["Symbol"],
                    "status": "failed",
                    "reason": str(e)
                })
        
        manager.session.refresh_gtt_cache()
        
        return {
            "adjusted": sanitize_for_json(adjusted),
            "failed": sanitize_for_json(failed),
            "count": len(adjusted) + len(failed)
        }

    def _get_manager(self, session_id: str) -> GTTManager:
        context = self._get_context(session_id)
        cmp_manager = context.session_cache.get_cmp_manager()
        return GTTManager(context.broker, cmp_manager, context.session_cache)

    def _build_strategy(self, session_id: str):
        context = self._get_context(session_id)
        return GTTStrategyAdapter(context)

    def _get_context(self, session_id: str):
        context = self._registry.get_session(session_id)
        if not context:
            raise ValueError("Invalid or expired session_id")
        return context


class GTTStrategyAdapter:
    def __init__(self, context) -> None:
        self._context = context

    def adjust_trigger_and_order_price(self, order_price: float, ltp: float):
        from core.multilevel_entry import MultiLevelEntryStrategy

        session_cache = self._context.session_cache
        cmp_manager = session_cache.get_cmp_manager()
        strategy = MultiLevelEntryStrategy(
            self._context.broker,
            cmp_manager,
            session_cache.get_holdings(),
            session_cache.get_entry_levels(),
            session_cache.get_gtt_cache(),
        )
        return strategy.adjust_trigger_and_order_price(order_price, ltp)
