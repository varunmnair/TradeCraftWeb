"""Dynamic Averaging BUY-only candidate evaluator — system-driven.

Generates DA BUY candidates just-in-time from holdings, entry strategy,
CMP, and OHLCV data. No manual DA configuration required.

DA BUY behaves like a reverse-trailing buyback mechanism:
- Generates DA BUY candidates only after meaningful price decline below average.
- Avoids buying during a falling move — uses trigger above CMP for reversal confirmation.
- Dynamically adjusts trigger offset based on regime, delta from avg, ATR, candle behavior, support.
- Determines DA legs and quantity dynamically.
"""

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

# Base trigger offsets per regime (percentage)
_BASE_OFFSETS: dict[str, float] = {
    "REVERSAL_LIKELY": 1.0,
    "NEUTRAL": 1.5,
    "STILL_FALLING": 2.0,
}

# Offset clamp bounds per regime (min, max)
_OFFSET_BOUNDS: dict[str, tuple[float, float]] = {
    "REVERSAL_LIKELY": (0.75, 1.50),
    "NEUTRAL": (1.00, 2.00),
    "STILL_FALLING": (1.50, 3.00),
}


def _is_valid_price(price) -> bool:
    return price is not None and not (isinstance(price, float) and math.isnan(price))


def _clamp(value: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(max_val, value))


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
        ReasonCode.INVALID_ENTRY_LEVEL_ORDER: "Correct Entry 1, Entry 2 and Entry 3 before generating orders.",
        ReasonCode.NO_AVERAGING_CAPACITY: "Allow the next Multi-Level Entry tranche to handle additional accumulation, or wait for a meaningful position reduction.",
        ReasonCode.PRICE_NOT_READY_FOR_DA: "Wait until price reaches the configured buyback level.",
        ReasonCode.LOW_PROFIT_OPPORTUNITY: "Wait for a better price or larger available capacity.",
        ReasonCode.ENTRY_STRATEGY_MISSING: "Upload an entry strategy CSV to configure this holding.",
    }
    return actions.get(code, "Review manually.")


def _fetch_ohlcv(symbol: str) -> list[dict]:
    """Fetch OHLCV data for a symbol. Returns empty list on failure."""
    try:
        from core.market_data.ohlcv_store import ensure_ohlcv, get_ohlcv_multi

        clean = symbol.replace("-BE", "").replace("#", "").upper()
        ensure_ohlcv([clean], days=90)
        data = get_ohlcv_multi([clean], days=90)
        return data.get(clean, [])
    except Exception as e:
        logger.warning("Failed to fetch OHLCV for %s: %s", symbol, e)
        return []


def _compute_dynamic_offset(
    regime: str,
    drop_from_avg_pct: float,
    atr: float,
    atr_pct: float,
    recent_candles: list[dict],
    cmp_price: float,
    support_price: float | None,
    support_held: bool,
    support_broken: bool,
) -> tuple[float, float]:
    """Calculate the dynamic trigger offset based on regime, market conditions, and support.

    Returns (final_offset_pct, total_adjustment).
    """
    base_offset = _BASE_OFFSETS.get(regime, 1.5)
    adjustment = 0.0

    # 1. Delta from average adjustment
    if 3 <= drop_from_avg_pct < 5:
        adjustment += 0.50
    elif 5 <= drop_from_avg_pct < 10:
        adjustment += 0.00
    elif 10 <= drop_from_avg_pct < 15:
        adjustment -= 0.25
    elif drop_from_avg_pct >= 15:
        adjustment -= 0.50

    # 2. ATR volatility adjustment
    if atr_pct > 4:
        adjustment += 0.25
    elif atr_pct < 2:
        adjustment -= 0.25

    # 3. Candle behavior adjustment
    if recent_candles and len(recent_candles) >= 2:
        last = recent_candles[-1]
        prev = recent_candles[-2]
        avg_vol = 0.0
        volumes = [c.get("volume", 0) for c in recent_candles if c.get("volume")]
        if volumes:
            avg_vol = sum(volumes) / len(volumes)

        strong_reversal = (
            last["close"] > prev["close"]
            and last["low"] > prev["low"]
            and last["close"] > last["open"]
            and avg_vol > 0
            and last.get("volume", 0) >= avg_vol
        )
        strong_fall = (
            last["close"] < prev["close"]
            and last["low"] < prev["low"]
            and last["close"] < last["open"]
            and avg_vol > 0
            and last.get("volume", 0) > avg_vol
        )

        if strong_reversal:
            adjustment -= 0.25
        elif strong_fall:
            adjustment += 0.25

    # 4. Support adjustment
    if support_price and support_price > 0 and atr > 0:
        distance = abs(cmp_price - support_price)
        if distance <= atr and not support_broken:
            adjustment -= 0.25
        elif support_broken:
            adjustment += 0.25

    final_offset = base_offset + adjustment
    min_bound, max_bound = _OFFSET_BOUNDS.get(regime, (1.0, 2.0))
    final_offset = _clamp(final_offset, min_bound, max_bound)

    return final_offset, adjustment


def _ensure_trigger_above_cmp(
    trigger_price: float, cmp: float, final_offset_pct: float, tick_size: float
) -> float:
    """Ensure trigger price is always above CMP after broker adjustment and rounding.

    If trigger <= CMP, recalculate from CMP and apply tick-size rounding upward.
    """
    if trigger_price > cmp:
        return trigger_price

    trigger_price = cmp * (1 + final_offset_pct / 100)
    trigger_price = round(round(trigger_price / tick_size) * tick_size, 2)

    if trigger_price <= cmp:
        tick = tick_size
        trigger_price = cmp + tick
        trigger_price = round(round(trigger_price / tick_size) * tick_size, 2)

    return trigger_price


class DynamicAveragingCandidateEvaluator(BaseCandidateEvaluator):
    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.DYNAMIC_AVERAGING

    def identify_candidates(
        self, context: CandidateContext
    ) -> tuple[list[NormalizedCandidate], list[SkippedCandidate]]:
        candidates: list[NormalizedCandidate] = []
        skipped: list[SkippedCandidate] = []
        holdings_map = context.get_holdings_map()
        entry_map = context.get_entry_levels_map()
        config = context.config

        for symbol, holding in holdings_map.items():
            exchange = "NSE"

            # 1. Entry strategy exists?
            entry = entry_map.get(symbol)
            if not entry:
                continue  # MLE evaluator handles missing strategies

            exchange = entry.get("exchange", "NSE")

            # 2. Guardrail: Trade already completed today
            if symbol in context.completed_trade_symbols:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.DYNAMIC_AVERAGING,
                        ReasonCode.TRADE_ALREADY_DONE,
                    )
                )
                continue

            # 3. CMP available
            ltp = context.cmp_manager.get_cmp(exchange, symbol)
            if not ltp or ltp <= 0:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.DYNAMIC_AVERAGING,
                        ReasonCode.DATA_UNAVAILABLE,
                    )
                )
                continue

            # 4. Thesis break (defense-in-depth)
            thesis_break_price = entry.get("thesis_break_price")
            if thesis_break_price is not None and ltp <= thesis_break_price:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.DYNAMIC_AVERAGING,
                        ReasonCode.THESIS_BREAK,
                        cmp=ltp,
                        technical_details=f"Thesis break at {thesis_break_price}",
                    )
                )
                continue

            # 5. Guardrail: Duplicate active GTT
            if symbol.upper() in context.existing_gtt_symbols:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.DYNAMIC_AVERAGING,
                        ReasonCode.DUPLICATE_ORDER,
                        cmp=ltp,
                    )
                )
                continue

            # 6. Holdings data
            held_qty = holding.get("quantity", 0) + holding.get("t1_quantity", 0)
            avg_price = holding.get("average_price", 0)
            invested_amount = avg_price * held_qty

            if held_qty <= 0:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.DYNAMIC_AVERAGING,
                        ReasonCode.NO_HOLDING,
                        cmp=ltp,
                    )
                )
                continue

            # 7. Entry levels valid and descending
            allocated = entry.get("Allocated", 0) or 0
            if allocated <= 0:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.DYNAMIC_AVERAGING,
                        ReasonCode.CONFIGURATION_MISSING,
                    )
                )
                continue

            entry_prices = []
            for key in ["entry1", "entry2", "entry3"]:
                try:
                    val = float(entry.get(key))
                    if _is_valid_price(val):
                        entry_prices.append(val)
                except (TypeError, ValueError):
                    continue

            if not entry_prices:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.DYNAMIC_AVERAGING,
                        ReasonCode.CONFIGURATION_MISSING,
                    )
                )
                continue

            indexed_prices = [(i + 1, p) for i, p in enumerate(entry_prices)]
            order_violation = validate_entry_level_order(indexed_prices)
            if order_violation is not None:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.DYNAMIC_AVERAGING,
                        ReasonCode.INVALID_ENTRY_LEVEL_ORDER,
                        technical_details=order_violation,
                    )
                )
                continue

            # 8. Calculate DA capacity (same tranche logic as MLE)
            num_entries = len(entry_prices)
            per_level_alloc = allocated / num_entries
            threshold = tranche_completion_threshold(
                per_level_alloc, ltp, config.tranche_completion_pct
            )

            cumulative_allocs = [per_level_alloc * (i + 1) for i in range(num_entries)]

            current_level = None
            for i, target_alloc in enumerate(cumulative_allocs):
                if invested_amount <= target_alloc:
                    current_level = i
                    break

            if current_level is None:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.DYNAMIC_AVERAGING,
                        ReasonCode.ALLOCATION_COMPLETE,
                        cmp=ltp,
                    )
                )
                continue

            da_capacity = cumulative_allocs[current_level] - invested_amount

            if da_capacity <= 0:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.DYNAMIC_AVERAGING,
                        ReasonCode.ALLOCATION_COMPLETE,
                        cmp=ltp,
                    )
                )
                continue

            if da_capacity <= threshold:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.DYNAMIC_AVERAGING,
                        ReasonCode.NO_AVERAGING_CAPACITY,
                        cmp=ltp,
                        technical_details=(
                            f"DA capacity {da_capacity:.0f} <= threshold {threshold:.0f}; "
                            f"tranche effectively complete"
                        ),
                    )
                )
                continue

            # 9. Minimum price decline check
            drop_pct = config.minimum_da_decline_pct
            decline_threshold = avg_price * (1 - drop_pct / 100)
            drop_from_avg_pct = ((avg_price - ltp) / avg_price * 100) if avg_price > 0 else 0

            if ltp > decline_threshold:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.DYNAMIC_AVERAGING,
                        ReasonCode.PRICE_NOT_READY_FOR_DA,
                        cmp=ltp,
                        technical_details=(
                            f"CMP {ltp:.2f} > decline threshold {decline_threshold:.2f} "
                            f"({drop_pct}% below avg {avg_price:.2f})"
                        ),
                    )
                )
                continue

            # 10. Fetch OHLCV and classify regime
            candles = _fetch_ohlcv(symbol)
            if not candles or len(candles) < 5:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.DYNAMIC_AVERAGING,
                        ReasonCode.DATA_UNAVAILABLE,
                        cmp=ltp,
                        technical_details="Insufficient OHLCV data for regime classification",
                    )
                )
                continue

            from core.da_regime import classify_regime

            regime_result = classify_regime(
                candles,
                ema_fast_period=config.ema_fast_period,
                ema_slow_period=config.ema_slow_period,
                volume_avg_days=config.volume_average_days,
                lookback_days=config.da_lookback_days,
            )

            # 11. Dynamic trigger offset from regime, ATR, delta, candles, support
            atr_pct = regime_result.atr_pct
            atr = regime_result.atr
            regime = regime_result.regime

            final_offset_pct, adjustment = _compute_dynamic_offset(
                regime=regime,
                drop_from_avg_pct=drop_from_avg_pct,
                atr=atr,
                atr_pct=atr_pct,
                recent_candles=regime_result.recent_candles,
                cmp_price=ltp,
                support_price=regime_result.support_price,
                support_held=regime_result.support_held,
                support_broken=regime_result.support_broken,
            )

            # 12. Trigger price calculation — always above CMP
            tick_size = 0.05 if ltp < 500 else 0.1
            trigger_price = ltp * (1 + final_offset_pct / 100)
            trigger_price = round(round(trigger_price / tick_size) * tick_size, 2)

            order_price, trigger_price = BaseEntryStrategy.adjust_trigger_and_order_price(
                trigger_price, ltp
            )

            # Validate trigger > CMP after broker adjustment
            trigger_price = _ensure_trigger_above_cmp(
                trigger_price, ltp, final_offset_pct, tick_size
            )

            # Re-apply broker adjustment if trigger was corrected
            if order_price is None or order_price <= 0:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.DYNAMIC_AVERAGING,
                        ReasonCode.BROKER_VALIDATION_FAILED,
                        cmp=ltp,
                    )
                )
                continue

            # 13. Leg decision
            max_da_legs = config.max_da_legs
            if regime == "REVERSAL_LIKELY":
                legs = 1
            elif da_capacity <= 0.50 * per_level_alloc:
                legs = 1
            elif regime == "STILL_FALLING" and da_capacity > 0.50 * per_level_alloc:
                legs = min(2, max_da_legs)
            elif regime == "NEUTRAL" and da_capacity > 0.70 * per_level_alloc:
                legs = min(2, max_da_legs)
            else:
                legs = 1

            # 14. Quantity per leg
            leg_amount = da_capacity / legs

            # Skip legs where leg_amount is below threshold
            if leg_amount <= threshold:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.DYNAMIC_AVERAGING,
                        ReasonCode.NO_AVERAGING_CAPACITY,
                        cmp=ltp,
                        technical_details=(
                            f"Per-leg amount {leg_amount:.0f} <= threshold {threshold:.0f}"
                        ),
                    )
                )
                continue

            if order_price is None or order_price <= 0:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.DYNAMIC_AVERAGING,
                        ReasonCode.BROKER_VALIDATION_FAILED,
                        cmp=ltp,
                    )
                )
                continue

            remaining_qty = math.floor(leg_amount / order_price)
            if remaining_qty <= 0:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.DYNAMIC_AVERAGING,
                        ReasonCode.BROKER_VALIDATION_FAILED,
                        cmp=ltp,
                        technical_details="Computed quantity is 0",
                    )
                )
                continue

            leg_qty = int(remaining_qty)
            actual_order_value = round(leg_qty * order_price, 2)

            # 15. Expected benefit vs cost
            expected_benefit = (avg_price - ltp) * leg_qty
            est_cost = actual_order_value * config.min_da_cost_pct / 100
            net_benefit = expected_benefit - est_cost

            if net_benefit < config.min_da_net_benefit:
                skipped.append(
                    _build_skipped(
                        symbol,
                        exchange,
                        StrategyType.DYNAMIC_AVERAGING,
                        ReasonCode.LOW_PROFIT_OPPORTUNITY,
                        cmp=ltp,
                        technical_details=(
                            f"Net benefit {net_benefit:.0f} < minimum {config.min_da_net_benefit:.0f} "
                            f"(benefit {expected_benefit:.0f}, cost {est_cost:.0f})"
                        ),
                    )
                )
                continue

            # 16. Build candidate(s)
            alloc_used_pct = (invested_amount / allocated * 100) if allocated > 0 else 0
            strategy_ref = entry.get("quality") or symbol

            for leg_i in range(legs):
                leg_label = f"DA{leg_i + 1}"
                reason_msg = (
                    f"Price is below average by {drop_from_avg_pct:.1f}%. "
                    f"DA buyback candidate generated with {regime} regime and "
                    f"{final_offset_pct:.2f}% reversal confirmation offset."
                )
                candidates.append(
                    NormalizedCandidate(
                        symbol=symbol,
                        exchange=exchange,
                        strategy_type=StrategyType.DYNAMIC_AVERAGING,
                        side="BUY",
                        status=CandidateStatus.WARNING,
                        status_severity=1,
                        signal=leg_label,
                        cmp=round(ltp, 2),
                        order_price=round(order_price, 2),
                        trigger_price=round(trigger_price, 2),
                        qty=leg_qty,
                        amount=actual_order_value,
                        allocation=allocated,
                        current_holding_qty=held_qty,
                        current_holding_value=round(invested_amount, 2),
                        allocation_used_percent=round(alloc_used_pct, 1),
                        level_or_leg=leg_label,
                        strategy_reference=strategy_ref,
                        reason_code=None,
                        reason_message=reason_msg,
                        suggested_action="Review quantity and trigger before confirming.",
                        is_selectable=True,
                        created_at=datetime.utcnow().isoformat() + "Z",
                        additional_details={
                            "regime": regime,
                            "reversal_score": regime_result.reversal_score,
                            "falling_score": regime_result.falling_score,
                            "atr": round(atr, 4),
                            "atr_pct": round(atr_pct, 4),
                            "avg_volume": regime_result.avg_volume,
                            "trigger_offset_pct": round(final_offset_pct, 4),
                            "offset_adjustment": round(adjustment, 4),
                            "base_offset": round(_BASE_OFFSETS.get(regime, 1.5), 2),
                            "da_capacity": round(da_capacity, 2),
                            "per_level_allocation": round(per_level_alloc, 2),
                            "invested_amount": round(invested_amount, 2),
                            "entry_level": f"E{current_level + 1}",
                            "drop_from_avg_pct": round(drop_from_avg_pct, 2),
                            "expected_benefit": round(expected_benefit, 2),
                            "estimated_cost": round(est_cost, 2),
                            "net_benefit": round(net_benefit, 2),
                            "total_legs": legs,
                            "support_price": regime_result.support_price,
                            "support_held": regime_result.support_held,
                            "support_broken": regime_result.support_broken,
                        },
                    )
                )

        return candidates, skipped
