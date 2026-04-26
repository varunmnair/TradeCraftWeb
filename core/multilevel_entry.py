import logging
import math
from typing import Dict, List, Tuple

from core.entry import BaseEntryStrategy, create_skipped_item, create_pending_cmp_item
from core.risk_manager import RiskManager


class MultiLevelEntryPlanner(BaseEntryStrategy):
    LTP_TRIGGER_VARIANCE_PERCENT = 0.15  # 15% configurable value
    ORDER_PRICE_BUFFER_PERCENT = 0.025  # 2.5% buffer

    def __init__(self, broker, cmp_manager, holdings, entry_levels, gtt_cache):
        super().__init__(broker, cmp_manager, holdings)
        self.entry_levels = entry_levels
        self.gtt_cache = gtt_cache
        self.risk_manager = RiskManager()
        self.skipped_items = []
        self.pending_cmp_items = []

    def _is_valid_price(self, price) -> bool:
        """Checks if a price is a valid, non-NaN number."""
        return price is not None and not (
            isinstance(price, float) and math.isnan(price)
        )

    def identify_candidates(self) -> List[Dict]:
        candidates = []
        existing_gtt_symbols = set()
        gtt_orders = self.broker.get_gtt_orders()
        for gtt_order in gtt_orders:
            if gtt_order.get("orders") and len(gtt_order["orders"]) > 0:
                if (
                    gtt_order.get("status") in ["active", "COMPLETED"]
                    and gtt_order["orders"][0]["transaction_type"] == "BUY"
                ):
                    if gtt_order.get("condition") and gtt_order["condition"].get(
                        "tradingsymbol"
                    ):
                        existing_gtt_symbols.add(
                            gtt_order["condition"]["tradingsymbol"].upper()
                        )

        from datetime import datetime

        trades = self.broker.trades()
        completed_trade_symbols = set()
        today = datetime.now().date()
        for trade in trades:
            trade_date = trade.get("fill_timestamp")
            if trade_date and trade_date.date() == today:
                completed_trade_symbols.add(trade.get("tradingsymbol").upper())

        for scrip in self.entry_levels:
            symbol = scrip.get("symbol")
            if not symbol:
                continue

            exchange = scrip.get("exchange", "NSE")

            if symbol.upper() in existing_gtt_symbols:
                self.skipped_items.append(
                    create_skipped_item(
                        symbol, "GTT already exists", exchange=exchange
                    )
                )
                continue

            if symbol.upper() in completed_trade_symbols:
                self.skipped_items.append(
                    create_skipped_item(
                        symbol, "Trade already completed today", exchange=exchange
                    )
                )
                continue

            allocated = scrip.get("Allocated")
            if (
                allocated is None
                or (isinstance(allocated, float) and math.isnan(allocated))
                or allocated == 0
            ):
                self.skipped_items.append(
                    create_skipped_item(
                        symbol, "Invalid or zero allocation", exchange=exchange
                    )
                )
                continue

            entry1 = scrip.get("entry1")
            entry2 = scrip.get("entry2")
            entry3 = scrip.get("entry3")
            is_entry1_valid = self._is_valid_price(entry1)
            is_entry2_valid = self._is_valid_price(entry2)
            is_entry3_valid = self._is_valid_price(entry3)
            num_entries = (
                (1 if is_entry1_valid else 0)
                + (1 if is_entry2_valid else 0)
                + (1 if is_entry3_valid else 0)
            )

            if num_entries == 0:
                self.skipped_items.append(
                    create_skipped_item(
                        symbol, "No valid entry levels", exchange=exchange
                    )
                )
                continue

            ltp = self.cmp_manager.get_cmp(exchange, symbol)

            if ltp is None or ltp == 0 or (isinstance(ltp, float) and math.isnan(ltp)):
                entry_levels_dict = {
                    "entry1": entry1 if is_entry1_valid else None,
                    "entry2": entry2 if is_entry2_valid else None,
                    "entry3": entry3 if is_entry3_valid else None,
                }
                self.pending_cmp_items.append(
                    create_pending_cmp_item(symbol, exchange, entry_levels_dict)
                )
                continue

            candidate_scrip = scrip.copy()
            candidate_scrip["ltp"] = ltp
            candidate_scrip["num_entries"] = num_entries
            candidate_scrip["is_entry1_valid"] = is_entry1_valid
            candidate_scrip["is_entry2_valid"] = is_entry2_valid
            candidate_scrip["is_entry3_valid"] = is_entry3_valid
            candidates.append(candidate_scrip)

        return candidates

    def _get_holding_details(
        self, holdings_map: Dict, symbol: str
    ) -> Tuple[float, float]:
        holding = holdings_map.get(symbol)
        if not holding:
            return 0, 0

        total_qty = holding.get("quantity", 0) + holding.get("t1_quantity", 0)
        average_price = holding.get("average_price", 0)
        return total_qty, average_price

    def _determine_entry_level(
        self, scrip: Dict, invested_amount: float, ltp: float
    ) -> Tuple[str, float, float]:
        num_entries = scrip["num_entries"]
        allocated = scrip["Allocated"]
        entry_allocated = allocated / num_entries if num_entries > 0 else 0

        entry_level_definitions = [
            {
                "level": "E1",
                "price": scrip.get("entry1"),
                "is_valid": scrip["is_entry1_valid"],
                "max_investment": entry_allocated,
            },
            {
                "level": "E2",
                "price": scrip.get("entry2"),
                "is_valid": scrip["is_entry2_valid"],
                "max_investment": 2 * entry_allocated,
            },
            {
                "level": "E3",
                "price": scrip.get("entry3"),
                "is_valid": scrip["is_entry3_valid"],
                "max_investment": allocated,
            },
        ]

        potential_levels = []
        for i, level_info in enumerate(entry_level_definitions):
            if (
                level_info["is_valid"]
                and self._is_valid_price(level_info["price"])
                and ltp <= level_info["price"]
            ):
                current_level_max_investment = (i + 1) * entry_allocated
                if i + 1 == num_entries:
                    current_level_max_investment = allocated

                if invested_amount < current_level_max_investment:
                    potential_levels.append((level_info, current_level_max_investment))

        if potential_levels:
            best_level, best_max_investment = min(
                potential_levels, key=lambda x: x[0]["price"]
            )
            return best_level["level"], best_level["price"], best_max_investment

        for i, level_info in enumerate(entry_level_definitions):
            if level_info["is_valid"] and self._is_valid_price(level_info["price"]):
                current_level_max_investment = (i + 1) * entry_allocated
                if i + 1 == num_entries:
                    current_level_max_investment = allocated

                if invested_amount < current_level_max_investment:
                    return (
                        level_info["level"],
                        level_info["price"],
                        current_level_max_investment,
                    )

        return None, None, 0  # type: ignore[return-value]

    def _calculate_quantity(self, amount_to_invest: float, entry_price: float) -> int:
        if entry_price is None or entry_price == 0:
            return 0
        return int(amount_to_invest / entry_price)

    def generate_plan(
        self, candidates: List[Dict], apply_risk_management: bool = False
    ) -> Dict:
        logging.debug("--- Generating Multi-Level Entry Plan ---")
        final_plan = []
        holdings_map = {
            h["tradingsymbol"].replace("#", "").replace("-BE", ""): h
            for h in self.holdings
        }

        for scrip in candidates:
            symbol = scrip["symbol"]
            exchange = scrip["exchange"]
            ltp = scrip["ltp"]
            allocated = scrip["Allocated"]

            total_qty, average_price = self._get_holding_details(holdings_map, symbol)
            invested_amount = total_qty * average_price

            if invested_amount >= allocated:
                self.skipped_items.append(
                    create_skipped_item(
                        symbol,
                        "Holding has reached or exceeded allocated amount",
                        exchange,
                        ltp,
                    )
                )
                continue

            entry_level, entry_price, target_investment = self._determine_entry_level(
                scrip, invested_amount, ltp
            )

            if not entry_level:
                self.skipped_items.append(
                    create_skipped_item(
                        symbol,
                        "Holding does not qualify for any entry level",
                        exchange,
                        ltp,
                    )
                )
                continue

            if not self._is_valid_price(entry_price):
                self.skipped_items.append(
                    create_skipped_item(
                        symbol,
                        "Invalid entry price for quantity calculation",
                        exchange,
                        ltp,
                        entry_level,
                    )
                )
                continue

            amount_to_invest = min(
                target_investment - invested_amount, allocated - invested_amount
            )

            scale_factor = 1.0
            risk_adj_str = "N/A"
            risk_reasons = ""

            if apply_risk_management:
                adjustments, risk_reasons = self._get_risk_adjustments(
                    exchange, symbol, ltp, scrip
                )

                scale_factor = adjustments.get("scale_factor", 1.0)
                sdt_cap_pct = adjustments.get("sdt_cap_pct")
                reserve_pct = adjustments.get("per_symbol_reserve_pct", 0.0)

                max_spendable = allocated * (1 - reserve_pct)
                amount_to_invest = min(
                    amount_to_invest, max_spendable - invested_amount
                )

                if sdt_cap_pct:
                    capped_investment = allocated * sdt_cap_pct
                    amount_to_invest = min(
                        amount_to_invest, capped_investment - invested_amount
                    )

                amount_to_invest *= scale_factor

                risk_adj_str = f"{scale_factor:.2f}{' (SDT Cap ' + str(sdt_cap_pct) + ')' if sdt_cap_pct else ''}"

            if amount_to_invest <= 0:
                reason = (
                    f"Amount is zero after risk rules. Reasons: {risk_reasons}"
                    if risk_reasons
                    else "No further investment needed"
                )
                self.skipped_items.append(
                    create_skipped_item(symbol, reason, exchange, ltp, entry_level)
                )
                continue

            order_price = (
                min(entry_price, round(ltp * (1 + self.ORDER_PRICE_BUFFER_PERCENT), 2))
                if entry_price > ltp
                else entry_price
            )
            order_price, trigger = self.adjust_trigger_and_order_price(order_price, ltp)

            qty = self._calculate_quantity(amount_to_invest, order_price)

            if qty == 0:
                self.skipped_items.append(
                    create_skipped_item(
                        symbol, "Computed quantity is 0", exchange, ltp, entry_level
                    )
                )
                continue

            variance = abs(ltp - trigger) / trigger if trigger > 0 else 0
            if variance > self.LTP_TRIGGER_VARIANCE_PERCENT:
                reason = f"LTP-trigger variance of {variance:.1%} exceeds threshold of {self.LTP_TRIGGER_VARIANCE_PERCENT:.1%}"
                self.skipped_items.append(
                    create_skipped_item(
                        symbol, reason, exchange, ltp, entry_level
                    )
                )
                continue

            final_plan.append(
                {
                    "symbol": symbol,
                    "exchange": exchange,
                    "price": order_price,
                    "trigger": trigger,
                    "qty": qty,
                    "ltp": round(ltp, 2),
                    "entry": entry_level,
                    "risk_adj": risk_adj_str,
                    "risk_reasons": risk_reasons,
                    "original_amount": (
                        amount_to_invest / scale_factor
                        if scale_factor != 0
                        else amount_to_invest
                    ),
                }
            )

        return {
            "plan": final_plan,
            "pending_cmp": self.pending_cmp_items,
            "skipped": self.skipped_items,
        }

    def _get_risk_adjustments(self, exchange, symbol, ltp, scrip):
        """Helper to fetch data and get risk adjustments for a single symbol."""
        from core.market_data.ohlcv_store import OhlcvStoreError, get_ohlcv

        try:
            quote = self.cmp_manager.get_quote(exchange, symbol)
            try:
                historical_data = get_ohlcv(symbol, days=200)
            except OhlcvStoreError as e:
                logging.warning(f"OHLCV data not available for {symbol}: {e}")
                historical_data = []
        except Exception as e:
            logging.error(f"Could not fetch risk data for {symbol}: {e}")
            self.skipped_items.append(
                create_skipped_item(
                    symbol,
                    "Failed to fetch risk data (quote/historical)",
                    exchange,
                    ltp,
                )
            )
            return {}, ""

        scrip_data_for_risk = {
            "ltp": ltp,
            "quote": quote,
            "historical": historical_data,
            "entry1": scrip.get("entry1"),
            "entry2": scrip.get("entry2"),
            "entry3": scrip.get("entry3"),
        }

        adjustments = self.risk_manager.assess_risk_and_get_adjustments(
            scrip_data_for_risk
        )
        risk_reasons = ", ".join(adjustments.get("reasons", []))
        return adjustments, risk_reasons

    def apply_risk_to_plan(self, draft_plan: List[Dict]) -> Dict:
        """Applies risk management to an existing draft plan."""
        final_plan = []
        logging.info(
            f"Applying risk management to {len(draft_plan)} symbols in the draft plan."
        )

        for order in draft_plan:
            symbol = order["symbol"]
            exchange = order["exchange"]
            ltp = order["ltp"]

            scrip = next((s for s in self.entry_levels if s["symbol"] == symbol), None)
            if not scrip:
                logging.warning(
                    f"Could not find original entry level data for {symbol}. Skipping risk analysis."
                )
                final_plan.append(order)
                continue

            adjustments, risk_reasons = self._get_risk_adjustments(
                exchange, symbol, ltp, scrip
            )

            scale_factor = adjustments.get("scale_factor", 1.0)
            sdt_cap_pct = adjustments.get("sdt_cap_pct")

            original_amount = order.get("original_amount")
            if original_amount is None:
                price = order.get("price", 0)
                qty = order.get("qty", 0)
                original_amount = price * qty

            amount_to_invest = original_amount * scale_factor

            new_qty = self._calculate_quantity(amount_to_invest, order["price"])

            if new_qty > 0:
                final_order = order.copy()
                final_order["qty"] = new_qty
                final_order["risk_adj"] = (
                    f"{scale_factor:.2f}{' (SDT Cap ' + str(sdt_cap_pct) + ')' if sdt_cap_pct else ''}"
                )
                final_order["risk_reasons"] = risk_reasons
                final_plan.append(final_order)
            else:
                reason = f"Qty became 0 after risk rules. Reasons: {risk_reasons}"
                self.skipped_items.append(
                    create_skipped_item(
                        symbol, reason, exchange, ltp, order["entry"]
                    )
                )

        return {
            "plan": final_plan,
            "pending_cmp": [],
            "skipped": self.skipped_items,
        }


# Backward compatibility alias
MultiLevelEntryStrategy = MultiLevelEntryPlanner
