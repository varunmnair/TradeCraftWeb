"""Multi-Level Entry candidate evaluator with corrected tranche logic."""

from __future__ import annotations

import logging
import math
from datetime import datetime

from core.candidates import (
    REASON_MESSAGES,
    CandidateStatus,
    NormalizedCandidate,
    ReasonCode,
    SkippedCandidate,
    StrategyType,
)
from core.entry import BaseEntryStrategy
from core.evaluators import (
    BaseCandidateEvaluator,
    CandidateContext,
    tranche_completion_threshold,
    validate_entry_level_order,
)

logger = logging.getLogger(__name__)

LTP_TRIGGER_VARIANCE_PERCENT = 0.15
ORDER_PRICE_BUFFER_PERCENT = 0.025


def _is_valid_price(price) -> bool:
    return price is not None and not (isinstance(price, float) and math.isnan(price))


def _build_skipped(
    symbol: str,
    exchange: str | None,
    strategy_type: StrategyType,
    reason_code: ReasonCode,
    cmp: float | None = None,
    level_or_leg: str | None = None,
    technical_details: str | None = None,
    suggested_action: str | None = None,
) -> SkippedCandidate:
    return SkippedCandidate(
        symbol=symbol,
        exchange=exchange,
        strategy_type=strategy_type,
        cmp=cmp,
        level_or_leg=level_or_leg,
        reason_code=reason_code,
        reason_message=REASON_MESSAGES[reason_code],
        suggested_action=suggested_action or _default_action(reason_code),
        technical_details=technical_details,
    )


def _default_action(code: ReasonCode) -> str:
    actions = {
        ReasonCode.DATA_UNAVAILABLE: "Refresh prices and try again.",
        ReasonCode.CONFIGURATION_MISSING: "Update the entry strategy with allocation and entry levels.",
        ReasonCode.PRICE_NOT_IN_RANGE: "Wait for price to enter the planned range.",
        ReasonCode.PRICE_TOO_FAR_FROM_PLAN: "Revise entry levels to match current market conditions.",
        ReasonCode.ALLOCATION_COMPLETE: "No action needed. Capital is fully deployed.",
        ReasonCode.DUPLICATE_ORDER: "Review the existing order or wait for it to execute.",
        ReasonCode.TRADE_ALREADY_DONE: "No action needed for today.",
        ReasonCode.MANUAL_REVIEW_REQUIRED: "Review entry levels and market conditions manually.",
        ReasonCode.THESIS_BREAK: "Review thesis and decide whether to continue or exit.",
        ReasonCode.BROKER_VALIDATION_FAILED: "Wait for price to stabilize within valid range.",
        ReasonCode.PRICE_ABOVE_OPPORTUNITY_WINDOW: "Wait for a pullback closer to the planned entry level.",
        ReasonCode.INVALID_ENTRY_LEVEL_ORDER: "Correct Entry 1, Entry 2 and Entry 3 before generating orders.",
        ReasonCode.NO_AVERAGING_CAPACITY: "Allow the next Multi-Level Entry tranche to handle additional accumulation.",
        ReasonCode.PRICE_NOT_READY_FOR_DA: "Wait until price reaches the configured buyback level.",
        ReasonCode.HOLDING_BETWEEN_LEVELS: "Wait until the position reaches the next tranche boundary, or rely on Dynamic Averaging.",
        ReasonCode.SYSTEM_ERROR: "Retry the operation.",
    }
    return actions.get(code, "Review manually.")


class MultiLevelCandidateEvaluator(BaseCandidateEvaluator):
    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.MULTI_LEVEL

    def identify_candidates(
        self, context: CandidateContext
    ) -> tuple[list[NormalizedCandidate], list[SkippedCandidate]]:
        candidates: list[NormalizedCandidate] = []
        skipped: list[SkippedCandidate] = []
        holdings_map = context.get_holdings_map()

        for scrip in context.entry_levels:
            symbol = scrip.get("symbol")
            if not symbol:
                continue

            if symbol in context.exclude_symbols:
                continue

            exchange = scrip.get("exchange", "NSE")
            allocated = scrip.get("Allocated")

            # Guardrail 1: Invalid allocation
            if (
                allocated is None
                or (isinstance(allocated, float) and math.isnan(allocated))
                or allocated == 0
            ):
                skipped.append(
                    _build_skipped(
                        symbol, exchange, StrategyType.MULTI_LEVEL, ReasonCode.CONFIGURATION_MISSING
                    )
                )
                continue

            # Guardrail 2: No valid entry levels
            entry1 = scrip.get("entry1")
            entry2 = scrip.get("entry2")
            entry3 = scrip.get("entry3")
            valid_entries = [(1, entry1), (2, entry2), (3, entry3)]
            valid_entries = [(n, p) for n, p in valid_entries if _is_valid_price(p)]

            if not valid_entries:
                skipped.append(
                    _build_skipped(
                        symbol, exchange, StrategyType.MULTI_LEVEL, ReasonCode.CONFIGURATION_MISSING
                    )
                )
                continue

            # Guardrail 2b: Entry level order validation (defense-in-depth)
            order_violation = validate_entry_level_order(valid_entries)
            if order_violation is not None:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.MULTI_LEVEL,
                        ReasonCode.INVALID_ENTRY_LEVEL_ORDER,
                        technical_details=order_violation,
                    )
                )
                continue

            # Guardrail 3: CMP unavailable
            ltp = context.cmp_manager.get_cmp(exchange, symbol)
            if ltp is None or ltp == 0 or (isinstance(ltp, float) and math.isnan(ltp)):
                skipped.append(
                    _build_skipped(
                        symbol, exchange, StrategyType.MULTI_LEVEL, ReasonCode.DATA_UNAVAILABLE
                    )
                )
                continue

            # Guardrail 4: Entry Opportunity Window
            entry_prices = {n: p for n, p in valid_entries}
            entry1_price = entry_prices.get(1)

            if entry1_price is not None and ltp > entry1_price:
                variance_pct = ((ltp - entry1_price) / entry1_price) * 100
                window_pct = context.config.entry_opportunity_window_pct

                if variance_pct > window_pct:
                    skipped.append(
                        _build_skipped(
                            symbol,
                            exchange,
                            StrategyType.MULTI_LEVEL,
                            ReasonCode.PRICE_ABOVE_OPPORTUNITY_WINDOW,
                            cmp=ltp,
                            technical_details=f"CMP {ltp:.2f} is {variance_pct:.1f}% above E1 {entry1_price:.2f} (window: {window_pct}%)",
                            suggested_action="Wait for a pullback closer to Entry 1.",
                        )
                    )
                    continue

            # Guardrail 5: Price too far below E3
            if 3 in entry_prices:
                max_below = context.config.max_below_entry3_percent / 100.0
                floor_price = entry_prices[3] * (1 - max_below)
                if ltp < floor_price:
                    skipped.append(
                        _build_skipped(
                            symbol,
                            exchange,
                            StrategyType.MULTI_LEVEL,
                            ReasonCode.PRICE_TOO_FAR_FROM_PLAN,
                            cmp=ltp,
                            level_or_leg=f"E3 ₹{entry_prices[3]:.0f}",
                            technical_details=f"CMP {ltp:.2f} is below floor {floor_price:.2f} (E3 {entry_prices[3]:.2f} - {context.config.max_below_entry3_percent}%)",
                        )
                    )
                    continue

            # Guardrail 6: Thesis break
            thesis_break = scrip.get("thesis_break_price")
            if thesis_break is not None and ltp <= thesis_break:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.MULTI_LEVEL,
                        ReasonCode.THESIS_BREAK,
                        cmp=ltp,
                        technical_details=f"Thesis break at ₹{thesis_break}",
                    )
                )
                continue

            # Guardrail 7: Duplicate active GTT
            if symbol.upper() in context.existing_gtt_symbols:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.MULTI_LEVEL,
                        ReasonCode.DUPLICATE_ORDER,
                        cmp=ltp,
                    )
                )
                continue

            # Guardrail 8: Trade completed today
            if symbol.upper() in context.completed_trade_symbols:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.MULTI_LEVEL,
                        ReasonCode.TRADE_ALREADY_DONE,
                        cmp=ltp,
                    )
                )
                continue

            # Holdings data
            holding = holdings_map.get(symbol)
            holding_qty = 0.0
            holding_value = 0.0
            avg_price = 0.0
            if holding:
                holding_qty = holding.get("quantity", 0) + holding.get("t1_quantity", 0)
                avg_price = holding.get("average_price", 0)
                holding_value = holding_qty * avg_price

            invested_amount = holding_value

            # Guardrail 9: Allocation exhausted
            if invested_amount >= allocated:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.MULTI_LEVEL,
                        ReasonCode.ALLOCATION_COMPLETE,
                        cmp=ltp,
                        technical_details=f"Invested ₹{invested_amount:.0f} >= Allocated ₹{allocated:.0f}",
                    )
                )
                continue

            # Tranche logic: determine next undeployed tranche using threshold
            num_entries = len(valid_entries)
            per_level_alloc = allocated / num_entries
            threshold = tranche_completion_threshold(per_level_alloc, ltp)

            # Sort entries by level number ascending (E1, E2, E3)
            sorted_entries = sorted(valid_entries, key=lambda x: x[0])

            # Find the next incomplete tranche
            next_tranche_idx = None
            for i in range(num_entries):
                tranche_target = per_level_alloc * (i + 1)
                remaining_gap = tranche_target - invested_amount

                if invested_amount >= tranche_target:
                    continue  # tranche fully complete
                elif remaining_gap <= threshold:
                    continue  # tranche effectively complete
                else:
                    next_tranche_idx = i
                    break

            if next_tranche_idx is None:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.MULTI_LEVEL,
                        ReasonCode.ALLOCATION_COMPLETE,
                        cmp=ltp,
                    )
                )
                continue

            next_level_no, next_entry_price = sorted_entries[next_tranche_idx]
            level_label = f"E{next_level_no}"

            # Guardrail: MLE fires only when the position is parked at a tranche boundary.
            # If the holding value is between boundaries (e.g. partially into the next
            # tranche), MLE stands down and Dynamic Averaging owns the symbol.
            boundary_amount = per_level_alloc * next_tranche_idx
            if abs(invested_amount - boundary_amount) > threshold:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.MULTI_LEVEL,
                        ReasonCode.HOLDING_BETWEEN_LEVELS,
                        cmp=ltp,
                        level_or_leg=level_label,
                        technical_details=(
                            f"Invested ₹{invested_amount:.0f} is between tranche boundaries "
                            f"(expected ₹{boundary_amount:.0f} ± ₹{threshold:.0f}). "
                            "Dynamic Averaging manages this position for now."
                        ),
                    )
                )
                continue

            # CMP must be within the opportunity window of the next tranche price
            max_allowed = next_entry_price * (1 + context.config.entry_opportunity_window_pct / 100)
            if ltp > max_allowed:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.MULTI_LEVEL,
                        ReasonCode.PRICE_NOT_IN_RANGE,
                        cmp=ltp,
                        level_or_leg=level_label,
                    )
                )
                continue

            # Calculate order amount: one tranche only
            amount_to_invest = min(per_level_alloc, allocated - invested_amount)

            # Price and trigger calculation
            order_price = (
                min(next_entry_price, round(ltp * (1 + ORDER_PRICE_BUFFER_PERCENT), 2))
                if next_entry_price > ltp
                else next_entry_price
            )
            order_price, trigger_price = BaseEntryStrategy.adjust_trigger_and_order_price(
                order_price, ltp
            )

            # Quantity
            if order_price is None or order_price == 0:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.MULTI_LEVEL,
                        ReasonCode.BROKER_VALIDATION_FAILED,
                        cmp=ltp,
                        level_or_leg=level_label,
                    )
                )
                continue

            qty = int(amount_to_invest / order_price)
            if qty == 0:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.MULTI_LEVEL,
                        ReasonCode.BROKER_VALIDATION_FAILED,
                        cmp=ltp,
                        level_or_leg=level_label,
                        technical_details="Computed quantity is 0",
                    )
                )
                continue

            # Actual order value = qty * order_price
            actual_order_value = round(qty * order_price, 2)

            # LTP-trigger variance check
            variance = abs(ltp - trigger_price) / trigger_price if trigger_price > 0 else 0
            if variance > LTP_TRIGGER_VARIANCE_PERCENT:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.MULTI_LEVEL,
                        ReasonCode.BROKER_VALIDATION_FAILED,
                        cmp=ltp,
                        level_or_leg=level_label,
                        technical_details=f"LTP-trigger variance {variance:.1%} > {LTP_TRIGGER_VARIANCE_PERCENT:.0%}",
                    )
                )
                continue

            # Build candidate
            alloc_used_pct = (invested_amount / allocated * 100) if allocated > 0 else 0
            strategy_ref = scrip.get("quality") or scrip.get("symbol")

            candidates.append(
                NormalizedCandidate(
                    symbol=symbol,
                    exchange=exchange,
                    strategy_type=StrategyType.MULTI_LEVEL,
                    side="BUY",
                    status=CandidateStatus.READY,
                    status_severity=0,
                    signal=level_label,
                    cmp=round(ltp, 2),
                    order_price=round(order_price, 2),
                    trigger_price=round(trigger_price, 2),
                    qty=qty,
                    amount=actual_order_value,
                    allocation=allocated,
                    current_holding_qty=holding_qty,
                    current_holding_value=round(holding_value, 2),
                    allocation_used_percent=round(alloc_used_pct, 1),
                    level_or_leg=level_label,
                    strategy_reference=strategy_ref,
                    reason_code=None,
                    reason_message=None,
                    suggested_action=None,
                    is_selectable=True,
                    created_at=datetime.utcnow().isoformat() + "Z",
                    additional_details={
                        "level_price": next_entry_price,
                        "tranche_number": next_tranche_idx + 1,
                        "total_tranches": num_entries,
                        "per_level_allocation": round(per_level_alloc, 2),
                    },
                )
            )

        return candidates, skipped
