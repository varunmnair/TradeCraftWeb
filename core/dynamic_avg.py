import math
from typing import Dict, List

from core.entry import create_skipped_item
from core.multilevel_entry import MultiLevelEntryPlanner


class DynamicAveragingPlanner:
    def __init__(
        self,
        *,
        broker,
        cmp_manager,
        holdings,
        entry_levels,
        gtt_cache,
        trigger_offset_factor=0.3,
    ):
        self.broker = broker
        self.cmp_manager = cmp_manager
        self.holdings = holdings
        self.entry_levels = entry_levels
        self.gtt_cache = gtt_cache
        self.trigger_offset_factor = trigger_offset_factor
        self.skipped_items = []

        self.multi_level_planner = MultiLevelEntryPlanner(
            self.broker,
            self.cmp_manager,
            self.holdings,
            self.entry_levels,
            self.gtt_cache,
        )

    def identify_candidates(self) -> List[Dict]:
        candidates = []
        entry_levels_map = {
            str(entry.get("symbol")).strip().upper(): entry
            for entry in self.entry_levels
            if isinstance(entry.get("symbol"), str) and entry.get("symbol", "").strip()
        }

        from datetime import datetime

        trades = self.broker.trades()
        completed_trade_symbols = set()
        today = datetime.now().date()

        for trade in trades:
            trade_date = trade.get("fill_timestamp")
            if trade_date and trade_date.date() == today:
                if trade.get("transaction_type") == "BUY":
                    completed_trade_symbols.add(trade.get("tradingsymbol").upper())

        for holding in self.holdings:
            symbol = (
                holding["tradingsymbol"].replace("#", "").replace("-BE", "").upper()
            )

            if symbol in completed_trade_symbols:
                self.skipped_items.append(
                    create_skipped_item(symbol, "Trade already completed today")
                )
                continue

            entry = entry_levels_map.get(symbol)

            da_enabled = (
                entry.get("DA Enabled", "").strip().upper() == "Y" if entry else False
            )
            entry_prices = []
            if entry:
                for key in ["entry1", "entry2", "entry3"]:
                    try:
                        val = float(entry.get(key))
                        if not math.isnan(val):
                            entry_prices.append(val)
                    except (TypeError, ValueError):
                        continue

            if not entry or not da_enabled or not entry_prices:
                self.skipped_items.append(
                    create_skipped_item(symbol, "No valid row in entry levels")
                )
                continue

            exchange = entry.get("exchange", "NSE")
            ltp = None
            try:
                ltp = self.cmp_manager.get_cmp(exchange, symbol)
            except RuntimeError as e:
                self.skipped_items.append(
                    create_skipped_item(symbol, "CMP not available", exchange=exchange)
                )
                continue
            except Exception as e:
                self.skipped_items.append(
                    create_skipped_item(symbol, "CMP not available", exchange=exchange)
                )
                continue

            if not ltp or ltp <= 0:
                self.skipped_items.append(
                    create_skipped_item(symbol, "CMP not available", exchange=exchange)
                )
                continue

            allocated = float(entry.get("Allocated", 0))
            if allocated < ltp:
                self.skipped_items.append(
                    create_skipped_item(
                        symbol,
                        f"Allocation {allocated} < LTP {ltp}",
                        exchange=exchange,
                        ltp=ltp,
                    )
                )
                continue

            held_qty = holding["quantity"] + holding.get("t1_quantity", 0)
            avg_price = holding["average_price"]
            invested_amount = avg_price * held_qty

            if invested_amount > allocated:
                self.skipped_items.append(
                    create_skipped_item(
                        symbol,
                        f"Invested amount {invested_amount:.2f} > allocated {allocated:.2f}",
                        exchange=exchange,
                        ltp=ltp,
                    )
                )
                continue

            entry_alloc_per_leg = allocated / len(entry_prices)
            cumulative_allocs = [
                entry_alloc_per_leg * (i + 1) for i in range(len(entry_prices))
            ]

            level = None
            for i, target_alloc in enumerate(cumulative_allocs):
                if invested_amount <= target_alloc:
                    level = i
                    break

            if level is None:
                self.skipped_items.append(
                    create_skipped_item(
                        symbol,
                        "Holding amount not in any entry level range",
                        exchange=exchange,
                        ltp=ltp,
                    )
                )
                continue

            da_legs = int(entry.get("DA Legs", 1))
            buyback_col = f"DA E{level+1} Buyback"
            da_buyback_at = float(entry.get(buyback_col, 5))
            da_trigger_offset = da_buyback_at * self.trigger_offset_factor

            threshold_price = avg_price * (1 - da_buyback_at / 100)
            if ltp > threshold_price:
                self.skipped_items.append(
                    create_skipped_item(
                        symbol,
                        f"LTP {ltp} not below threshold {threshold_price:.2f}",
                        exchange=exchange,
                        ltp=ltp,
                    )
                )
                continue

            candidates.append(
                {
                    "symbol": symbol,
                    "exchange": exchange,
                    "ltp": ltp,
                    "da_legs": da_legs,
                    "da_trigger_offset": da_trigger_offset,
                    "entry_level": f"E{level+1}",
                    "level_idx": level,
                    "invested_amount": invested_amount,
                    "cumulative_allocs": cumulative_allocs,
                    "allocated": allocated,
                }
            )

        return candidates

    def generate_plan(
        self, candidates: List[Dict], apply_risk_management: bool = False
    ) -> Dict:
        plan = []
        holdings_map = {
            h["tradingsymbol"].replace("#", "").replace("-BE", ""): h
            for h in self.holdings
        }

        for c in candidates:
            symbol = c["symbol"]
            exchange = c["exchange"]
            ltp = c["ltp"]
            da_legs = c["da_legs"]
            da_trigger_offset = c["da_trigger_offset"]

            level_idx = c["level_idx"]
            cumulative_allocs = c["cumulative_allocs"]
            invested_amount = c["invested_amount"]

            target_allocation_for_level = cumulative_allocs[level_idx]
            amount_to_invest = target_allocation_for_level - invested_amount

            entry_alloc_per_leg = cumulative_allocs[0]
            if amount_to_invest > (entry_alloc_per_leg * 0.75):
                self.skipped_items.append(
                    create_skipped_item(
                        symbol,
                        f"Remaining amount {amount_to_invest:.2f} > 75% of leg allocation",
                        exchange=exchange,
                        ltp=ltp,
                    )
                )
                continue

            if amount_to_invest <= 0:
                self.skipped_items.append(
                    create_skipped_item(
                        symbol,
                        "No amount to invest for this level",
                        exchange=exchange,
                        ltp=ltp,
                    )
                )
                continue

            remaining_qty = math.floor(amount_to_invest / ltp)

            if remaining_qty <= 0:
                self.skipped_items.append(
                    create_skipped_item(
                        symbol,
                        "Invalid quantity",
                        exchange=exchange,
                        ltp=ltp,
                    )
                )
                continue

            leg_qty = int(remaining_qty / da_legs)

            if leg_qty <= 0:
                self.skipped_items.append(
                    create_skipped_item(
                        symbol,
                        "Invalid quantity",
                        exchange=exchange,
                        ltp=ltp,
                    )
                )
                continue

            trigger_price = round(ltp * (1 + da_trigger_offset / 100), 2)
            order_price, trigger_price = (
                self.multi_level_planner.adjust_trigger_and_order_price(
                    trigger_price, ltp
                )
            )

            risk_adj_str = "N/A"
            risk_reasons = ""
            scale_factor = 1.0

            if apply_risk_management:
                adjustments, risk_reasons = self.multi_level_planner._get_risk_adjustments(
                    exchange, symbol, ltp,
                    {"entry1": c.get("entry1"), "entry2": c.get("entry2"), "entry3": c.get("entry3")}
                )
                scale_factor = adjustments.get("scale_factor", 1.0)
                sdt_cap_pct = adjustments.get("sdt_cap_pct")

                amount_to_invest *= scale_factor

                if sdt_cap_pct:
                    capped_investment = c["allocated"] * sdt_cap_pct
                    amount_to_invest = min(
                        amount_to_invest, capped_investment - invested_amount
                    )

                leg_qty = int(math.floor(amount_to_invest / ltp / da_legs))

                if leg_qty <= 0:
                    self.skipped_items.append(
                        create_skipped_item(
                            symbol,
                            f"Qty became 0 after risk rules. Reasons: {risk_reasons}",
                            exchange=exchange,
                            ltp=ltp,
                        )
                    )
                    continue

                risk_adj_str = f"{scale_factor:.2f}{' (SDT Cap ' + str(sdt_cap_pct) + ')' if sdt_cap_pct else ''}"

            for i in range(da_legs):
                plan.append(
                    {
                        "symbol": symbol,
                        "exchange": exchange,
                        "price": order_price,
                        "trigger": trigger_price,
                        "qty": leg_qty,
                        "ltp": round(ltp, 2),
                        "leg": f"DA{i+1}",
                        "entry": c["entry_level"],
                        "risk_adj": risk_adj_str,
                        "risk_reasons": risk_reasons,
                    }
                )

        return {
            "plan": plan,
            "skipped": self.skipped_items,
        }
