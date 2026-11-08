"""Tests for core/evaluators/dynamic_avg.py — system-driven DA BUY-only candidate evaluator.

Covers:
- All skip reasons (missing strategy, trade done, CMP unavailable, thesis break, duplicate GTT, etc.)
- DA capacity and tranche completion threshold
- Minimum decline check
- Regime-based candidate generation
- Dynamic offset calculation (delta, ATR, candle, support adjustments)
- Trigger always above CMP
- Leg determination logic
- Benefit/cost guard
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.candidates import CandidateStatus, ReasonCode, StrategyType
from core.evaluators import CandidateContext
from core.evaluators.dynamic_avg import (
    DynamicAveragingCandidateEvaluator,
    _compute_dynamic_offset,
    _ensure_trigger_above_cmp,
)
from core.strategy_config import StrategyConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cmp_manager(prices: dict[str, float] | None = None) -> MagicMock:
    mgr = MagicMock()
    mgr.get_cmp = MagicMock(side_effect=lambda ex, sym: (prices or {}).get(sym))
    return mgr


def _make_candles(n: int = 20, base_price: float = 100.0, trend: str = "down") -> list[dict]:
    """Generate synthetic OHLCV candles for regime testing."""
    candles = []
    price = base_price
    for i in range(n):
        if trend == "down":
            close = price * (1 - 0.005 * (n - i))
        elif trend == "up":
            close = price * (1 + 0.005 * (n - i))
        else:
            close = price
        candles.append({
            "date": f"2025-01-{i + 1:02d}",
            "open": close * 0.998,
            "high": close * 1.005,
            "low": close * 0.995,
            "close": close,
            "volume": 100000,
        })
    return candles


def _make_context(
    entry_levels: list[dict],
    holdings: list[dict],
    cmp_prices: dict[str, float] | None = None,
    completed_trades: set[str] | None = None,
    existing_gtt: set[str] | None = None,
    config: StrategyConfig | None = None,
) -> CandidateContext:
    return CandidateContext(
        entry_levels=entry_levels,
        holdings=holdings,
        cmp_manager=_make_cmp_manager(cmp_prices or {}),
        broker=MagicMock(),
        gtt_cache=[],
        completed_trade_symbols=completed_trades or set(),
        config=config or StrategyConfig(),
        existing_gtt_symbols=existing_gtt or set(),
    )


def _base_entry(symbol: str = "TEST", **overrides) -> dict:
    entry = {
        "symbol": symbol,
        "Allocated": 30000,
        "Quality": "A",
        "exchange": "NSE",
        "entry1": 100.0,
        "entry2": 95.0,
        "entry3": 90.0,
        "thesis_break_price": None,
    }
    entry.update(overrides)
    return entry


def _base_holding(symbol: str = "TEST", qty: int = 500, avg: float = 105.0) -> dict:
    return {
        "tradingsymbol": symbol,
        "quantity": qty,
        "t1_quantity": 0,
        "average_price": avg,
        "exchange": "NSE",
    }


EVALUATOR = DynamicAveragingCandidateEvaluator()


def _patch_ohlcv_regime(
    regime: str = "NEUTRAL",
    atr: float = 2.0,
    atr_pct: float = 2.0,
    support_price: float | None = None,
    support_held: bool = False,
    support_broken: bool = False,
):
    """Context manager that patches OHLCV fetch and regime classification."""
    from core.da_regime import RegimeResult

    mock_result = RegimeResult(
        regime=regime,
        reversal_score=6 if regime == "REVERSAL_LIKELY" else 2,
        falling_score=2 if regime == "REVERSAL_LIKELY" else 6,
        atr=atr,
        atr_pct=atr_pct,
        avg_volume=100000,
        support_price=support_price,
        support_held=support_held,
        support_broken=support_broken,
        recent_candles=_make_candles(5, 98.0, "up" if regime == "REVERSAL_LIKELY" else "down"),
    )

    candles = _make_candles(20, 100.0, "down" if regime == "STILL_FALLING" else "up")

    patches = {
        "fetch_ohlcv": patch(
            "core.evaluators.dynamic_avg._fetch_ohlcv",
            return_value=candles,
        ),
        "classify_regime": patch(
            "core.da_regime.classify_regime",
            return_value=mock_result,
        ),
    }
    return patches


def _make_config(**overrides) -> StrategyConfig:
    cfg = StrategyConfig()
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


# ---------------------------------------------------------------------------
# 1. Silent skip for missing entry strategy
# ---------------------------------------------------------------------------


class TestMissingEntryStrategy:
    def test_no_entry_strategy_no_candidates(self):
        holding = _base_holding()
        ctx = _make_context([], [holding], cmp_prices={"TEST": 98.0})
        candidates, skipped = EVALUATOR.identify_candidates(ctx)
        da_candidates = [c for c in candidates if c.strategy_type == StrategyType.DYNAMIC_AVERAGING]
        assert len(da_candidates) == 0

    def test_no_entry_strategy_no_skip_record(self):
        holding = _base_holding()
        ctx = _make_context([], [holding], cmp_prices={"TEST": 98.0})
        _, skipped = EVALUATOR.identify_candidates(ctx)
        da_skipped = [s for s in skipped if s.strategy_type == StrategyType.DYNAMIC_AVERAGING]
        assert len(da_skipped) == 0


# ---------------------------------------------------------------------------
# 2. Trade already done
# ---------------------------------------------------------------------------


class TestTradeAlreadyDone:
    def test_completed_trade_skips(self):
        entry = _base_entry()
        holding = _base_holding()
        ctx = _make_context(
            [entry], [holding], cmp_prices={"TEST": 98.0}, completed_trades={"TEST"}
        )
        _, skipped = EVALUATOR.identify_candidates(ctx)
        da_skipped = [s for s in skipped if s.strategy_type == StrategyType.DYNAMIC_AVERAGING]
        trade_skips = [s for s in da_skipped if s.reason_code == ReasonCode.TRADE_ALREADY_DONE]
        assert len(trade_skips) == 1


# ---------------------------------------------------------------------------
# 3. CMP unavailable
# ---------------------------------------------------------------------------


class TestCMPUnavailable:
    def test_no_cmp_skips(self):
        entry = _base_entry()
        holding = _base_holding()
        ctx = _make_context([entry], [holding], cmp_prices={})
        _, skipped = EVALUATOR.identify_candidates(ctx)
        da_skipped = [s for s in skipped if s.strategy_type == StrategyType.DYNAMIC_AVERAGING]
        data_skips = [s for s in da_skipped if s.reason_code == ReasonCode.DATA_UNAVAILABLE]
        assert len(data_skips) == 1


# ---------------------------------------------------------------------------
# 4. Thesis break
# ---------------------------------------------------------------------------


class TestThesisBreak:
    def test_thesis_break_price_skip(self):
        entry = _base_entry(thesis_break_price=100.0)
        holding = _base_holding()
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 98.0})
        _, skipped = EVALUATOR.identify_candidates(ctx)
        da_skipped = [s for s in skipped if s.strategy_type == StrategyType.DYNAMIC_AVERAGING]
        thesis_skips = [s for s in da_skipped if s.reason_code == ReasonCode.THESIS_BREAK]
        assert len(thesis_skips) == 1

    def test_cmp_above_thesis_break_not_skipped(self):
        entry = _base_entry(thesis_break_price=90.0)
        holding = _base_holding(qty=50, avg=105.0)
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 95.0})
        _, skipped = EVALUATOR.identify_candidates(ctx)
        da_skipped = [s for s in skipped if s.strategy_type == StrategyType.DYNAMIC_AVERAGING]
        thesis_skips = [s for s in da_skipped if s.reason_code == ReasonCode.THESIS_BREAK]
        assert len(thesis_skips) == 0


# ---------------------------------------------------------------------------
# 5. Duplicate GTT
# ---------------------------------------------------------------------------


class TestDuplicateGTT:
    def test_existing_gtt_skips(self):
        entry = _base_entry()
        holding = _base_holding(qty=50, avg=105.0)
        ctx = _make_context(
            [entry], [holding], cmp_prices={"TEST": 98.0}, existing_gtt={"TEST"}
        )
        _, skipped = EVALUATOR.identify_candidates(ctx)
        da_skipped = [s for s in skipped if s.strategy_type == StrategyType.DYNAMIC_AVERAGING]
        dup_skips = [s for s in da_skipped if s.reason_code == ReasonCode.DUPLICATE_ORDER]
        assert len(dup_skips) == 1


# ---------------------------------------------------------------------------
# 6. No holding / zero qty
# ---------------------------------------------------------------------------


class TestNoHolding:
    def test_zero_qty_skips(self):
        entry = _base_entry()
        holding = _base_holding(qty=0)
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 98.0})
        _, skipped = EVALUATOR.identify_candidates(ctx)
        da_skipped = [s for s in skipped if s.strategy_type == StrategyType.DYNAMIC_AVERAGING]
        no_hold = [s for s in da_skipped if s.reason_code == ReasonCode.NO_HOLDING]
        assert len(no_hold) == 1


# ---------------------------------------------------------------------------
# 7. Configuration missing
# ---------------------------------------------------------------------------


class TestConfigurationMissing:
    def test_zero_allocation_skips(self):
        entry = _base_entry(Allocated=0)
        holding = _base_holding(qty=50, avg=105.0)
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 98.0})
        _, skipped = EVALUATOR.identify_candidates(ctx)
        da_skipped = [s for s in skipped if s.strategy_type == StrategyType.DYNAMIC_AVERAGING]
        config_skips = [s for s in da_skipped if s.reason_code == ReasonCode.CONFIGURATION_MISSING]
        assert len(config_skips) == 1

    def test_no_entry_prices_skips(self):
        entry = _base_entry(entry1=None, entry2=None, entry3=None)
        holding = _base_holding(qty=50, avg=105.0)
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 98.0})
        _, skipped = EVALUATOR.identify_candidates(ctx)
        da_skipped = [s for s in skipped if s.strategy_type == StrategyType.DYNAMIC_AVERAGING]
        config_skips = [s for s in da_skipped if s.reason_code == ReasonCode.CONFIGURATION_MISSING]
        assert len(config_skips) == 1


# ---------------------------------------------------------------------------
# 8. Invalid entry level order
# ---------------------------------------------------------------------------


class TestInvalidEntryLevelOrder:
    def test_non_descending_skips(self):
        entry = _base_entry(entry1=88.50, entry2=85.00, entry3=88.00)
        holding = _base_holding(qty=50, avg=105.0)
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 86.0})
        _, skipped = EVALUATOR.identify_candidates(ctx)
        da_skipped = [s for s in skipped if s.strategy_type == StrategyType.DYNAMIC_AVERAGING]
        invalid_order = [
            s for s in da_skipped if s.reason_code == ReasonCode.INVALID_ENTRY_LEVEL_ORDER
        ]
        assert len(invalid_order) == 1


# ---------------------------------------------------------------------------
# 9. Allocation complete
# ---------------------------------------------------------------------------


class TestAllocationComplete:
    def test_fully_invested_skips(self):
        entry = _base_entry(Allocated=30000, entry1=100, entry2=95, entry3=90)
        holding = _base_holding(qty=300, avg=100.0)  # invested = 30000 = allocated
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 93.0})
        _, skipped = EVALUATOR.identify_candidates(ctx)
        da_skipped = [s for s in skipped if s.strategy_type == StrategyType.DYNAMIC_AVERAGING]
        alloc_complete = [s for s in da_skipped if s.reason_code == ReasonCode.ALLOCATION_COMPLETE]
        assert len(alloc_complete) == 1


# ---------------------------------------------------------------------------
# 10. No averaging capacity
# ---------------------------------------------------------------------------


class TestNoAveragingCapacity:
    def test_capacity_below_threshold_skips(self):
        # per_level = 30000/3 = 10000
        # invested = 19400 → level 1, max_allowed = 20000, capacity = 600
        # threshold = max(10000*0.08, 93) = max(800, 93) = 800
        # 600 <= 800 → skip
        entry = _base_entry(Allocated=30000, entry1=100, entry2=95, entry3=90)
        holding = _base_holding(qty=194, avg=100.0)  # invested = 19400
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 93.0})
        _, skipped = EVALUATOR.identify_candidates(ctx)
        da_skipped = [s for s in skipped if s.strategy_type == StrategyType.DYNAMIC_AVERAGING]
        capacity_skips = [
            s for s in da_skipped if s.reason_code == ReasonCode.NO_AVERAGING_CAPACITY
        ]
        assert len(capacity_skips) == 1

    def test_capacity_at_threshold_boundary_skips(self):
        # invested = 19200 → level 1, max_allowed = 20000, capacity = 800
        # threshold = max(800, 93) = 800 → 800 <= 800 → skip
        entry = _base_entry(Allocated=30000, entry1=100, entry2=95, entry3=90)
        holding = _base_holding(qty=192, avg=100.0)  # invested = 19200
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 93.0})
        _, skipped = EVALUATOR.identify_candidates(ctx)
        da_skipped = [s for s in skipped if s.strategy_type == StrategyType.DYNAMIC_AVERAGING]
        capacity_skips = [
            s for s in da_skipped if s.reason_code == ReasonCode.NO_AVERAGING_CAPACITY
        ]
        assert len(capacity_skips) == 1


# ---------------------------------------------------------------------------
# 11. Price not ready for DA (decline check)
# ---------------------------------------------------------------------------


class TestPriceNotReadyForDA:
    def test_price_above_decline_threshold_skips(self):
        # avg=105, drop_pct=5% → decline_threshold = 105*0.95 = 99.75
        # CMP=102 > 99.75 → skip
        entry = _base_entry(Allocated=30000, entry1=100, entry2=95, entry3=90)
        holding = _base_holding(qty=100, avg=105.0)  # invested = 10500
        config = _make_config(minimum_da_decline_pct=5.0)
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 102.0}, config=config)
        _, skipped = EVALUATOR.identify_candidates(ctx)
        da_skipped = [s for s in skipped if s.strategy_type == StrategyType.DYNAMIC_AVERAGING]
        price_skips = [
            s for s in da_skipped if s.reason_code == ReasonCode.PRICE_NOT_READY_FOR_DA
        ]
        assert len(price_skips) == 1
        assert "decline threshold" in price_skips[0].technical_details

    def test_price_below_decline_threshold_passes(self):
        # avg=105, drop_pct=5% → threshold=99.75, CMP=98 < 99.75 → passes
        entry = _base_entry(Allocated=30000, entry1=100, entry2=95, entry3=90)
        holding = _base_holding(qty=100, avg=105.0)
        config = _make_config(minimum_da_decline_pct=5.0)
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 98.0}, config=config)

        patches = _patch_ohlcv_regime("REVERSAL_LIKELY")
        with patches["fetch_ohlcv"], patches["classify_regime"]:
            candidates, skipped = EVALUATOR.identify_candidates(ctx)

        da_skipped = [s for s in skipped if s.strategy_type == StrategyType.DYNAMIC_AVERAGING]
        price_skips = [
            s for s in da_skipped if s.reason_code == ReasonCode.PRICE_NOT_READY_FOR_DA
        ]
        assert len(price_skips) == 0


# ---------------------------------------------------------------------------
# 12. Candidate generation (happy path)
# ---------------------------------------------------------------------------


class TestCandidateGeneration:
    def test_generates_buy_candidate(self):
        entry = _base_entry(Allocated=30000, entry1=100, entry2=95, entry3=90)
        holding = _base_holding(qty=50, avg=105.0)  # invested = 5250
        config = _make_config(minimum_da_decline_pct=5.0)
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 93.0}, config=config)

        patches = _patch_ohlcv_regime("REVERSAL_LIKELY")
        with patches["fetch_ohlcv"], patches["classify_regime"]:
            candidates, skipped = EVALUATOR.identify_candidates(ctx)

        da_cands = [c for c in candidates if c.strategy_type == StrategyType.DYNAMIC_AVERAGING]
        assert len(da_cands) >= 1
        assert da_cands[0].side == "BUY"
        assert da_cands[0].status == CandidateStatus.WARNING

    def test_candidate_has_regime_in_details(self):
        entry = _base_entry(Allocated=30000, entry1=100, entry2=95, entry3=90)
        holding = _base_holding(qty=50, avg=105.0)
        config = _make_config(minimum_da_decline_pct=5.0)
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 93.0}, config=config)

        patches = _patch_ohlcv_regime("REVERSAL_LIKELY")
        with patches["fetch_ohlcv"], patches["classify_regime"]:
            candidates, _ = EVALUATOR.identify_candidates(ctx)

        da_cands = [c for c in candidates if c.strategy_type == StrategyType.DYNAMIC_AVERAGING]
        assert da_cands[0].additional_details["regime"] == "REVERSAL_LIKELY"

    def test_candidate_all_are_buy(self):
        entry = _base_entry(Allocated=30000, entry1=100, entry2=95, entry3=90)
        holding = _base_holding(qty=50, avg=105.0)
        config = _make_config(minimum_da_decline_pct=5.0)
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 93.0}, config=config)

        patches = _patch_ohlcv_regime("STILL_FALLING")
        with patches["fetch_ohlcv"], patches["classify_regime"]:
            candidates, _ = EVALUATOR.identify_candidates(ctx)

        for c in candidates:
            assert c.side == "BUY", f"{c.symbol} has side={c.side}, expected BUY"

    def test_candidate_has_all_required_fields(self):
        entry = _base_entry(Allocated=30000, entry1=100, entry2=95, entry3=90)
        holding = _base_holding(qty=50, avg=105.0)
        config = _make_config(minimum_da_decline_pct=5.0)
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 93.0}, config=config)

        patches = _patch_ohlcv_regime("NEUTRAL")
        with patches["fetch_ohlcv"], patches["classify_regime"]:
            candidates, _ = EVALUATOR.identify_candidates(ctx)

        da_cands = [c for c in candidates if c.strategy_type == StrategyType.DYNAMIC_AVERAGING]
        assert len(da_cands) >= 1
        c = da_cands[0]
        details = c.additional_details
        assert "regime" in details
        assert "drop_from_avg_pct" in details
        assert "trigger_offset_pct" in details
        assert "da_capacity" in details
        assert "expected_benefit" in details
        assert "estimated_cost" in details
        assert "net_benefit" in details
        assert "total_legs" in details
        assert "base_offset" in details
        assert "offset_adjustment" in details

    def test_reason_message_includes_regime_and_offset(self):
        entry = _base_entry(Allocated=30000, entry1=100, entry2=95, entry3=90)
        holding = _base_holding(qty=50, avg=105.0)
        config = _make_config(minimum_da_decline_pct=5.0)
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 93.0}, config=config)

        patches = _patch_ohlcv_regime("REVERSAL_LIKELY")
        with patches["fetch_ohlcv"], patches["classify_regime"]:
            candidates, _ = EVALUATOR.identify_candidates(ctx)

        da_cands = [c for c in candidates if c.strategy_type == StrategyType.DYNAMIC_AVERAGING]
        msg = da_cands[0].reason_message
        assert "REVERSAL_LIKELY" in msg
        assert "below average" in msg
        assert "offset" in msg


# ---------------------------------------------------------------------------
# 13. Trigger offset varies by regime
# ---------------------------------------------------------------------------


class TestTriggerOffsetByRegime:
    def _get_trigger_offset(self, regime: str) -> float:
        entry = _base_entry(Allocated=30000, entry1=100, entry2=95, entry3=90)
        holding = _base_holding(qty=50, avg=105.0)
        config = _make_config(minimum_da_decline_pct=5.0)
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 93.0}, config=config)

        patches = _patch_ohlcv_regime(regime)
        with patches["fetch_ohlcv"], patches["classify_regime"]:
            candidates, _ = EVALUATOR.identify_candidates(ctx)

        da_cands = [c for c in candidates if c.strategy_type == StrategyType.DYNAMIC_AVERAGING]
        if da_cands:
            return da_cands[0].additional_details["trigger_offset_pct"]
        return 0.0

    def test_reversal_offset_smaller(self):
        reversal = self._get_trigger_offset("REVERSAL_LIKELY")
        neutral = self._get_trigger_offset("NEUTRAL")
        still_falling = self._get_trigger_offset("STILL_FALLING")
        assert reversal <= neutral <= still_falling


# ---------------------------------------------------------------------------
# 14. Legs decision by regime
# ---------------------------------------------------------------------------


class TestLegsByRegime:
    def test_reversal_always_one_leg(self):
        entry = _base_entry(Allocated=30000, entry1=100, entry2=95, entry3=90)
        holding = _base_holding(qty=50, avg=105.0)
        config = _make_config(minimum_da_decline_pct=5.0)
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 93.0}, config=config)

        patches = _patch_ohlcv_regime("REVERSAL_LIKELY")
        with patches["fetch_ohlcv"], patches["classify_regime"]:
            candidates, _ = EVALUATOR.identify_candidates(ctx)

        da_cands = [c for c in candidates if c.strategy_type == StrategyType.DYNAMIC_AVERAGING]
        assert len(da_cands) == 1
        assert da_cands[0].additional_details["total_legs"] == 1

    def test_capacity_below_50_pct_one_leg(self):
        # per_level_alloc = 30000/3 = 10000
        # invested = 5250, level 0, capacity = 10000 - 5250 = 4750
        # 4750 < 0.50 * 10000 = 5000 → 1 leg
        entry = _base_entry(Allocated=30000, entry1=100, entry2=95, entry3=90)
        holding = _base_holding(qty=52, avg=101.0)  # invested = 5252
        config = _make_config(minimum_da_decline_pct=5.0)
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 93.0}, config=config)

        patches = _patch_ohlcv_regime("STILL_FALLING")
        with patches["fetch_ohlcv"], patches["classify_regime"]:
            candidates, _ = EVALUATOR.identify_candidates(ctx)

        da_cands = [c for c in candidates if c.strategy_type == StrategyType.DYNAMIC_AVERAGING]
        if da_cands:
            assert da_cands[0].additional_details["total_legs"] == 1

    def test_still_falling_large_capacity_two_legs(self):
        # per_level_alloc = 60000/3 = 20000
        # invested = 5250, level 0, capacity = 20000 - 5250 = 14750
        # 14750 > 0.50 * 20000 = 10000, STILL_FALLING → 2 legs
        entry = _base_entry(Allocated=60000, entry1=100, entry2=95, entry3=90)
        holding = _base_holding(qty=50, avg=105.0)
        config = _make_config(minimum_da_decline_pct=5.0)
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 93.0}, config=config)

        patches = _patch_ohlcv_regime("STILL_FALLING")
        with patches["fetch_ohlcv"], patches["classify_regime"]:
            candidates, _ = EVALUATOR.identify_candidates(ctx)

        da_cands = [c for c in candidates if c.strategy_type == StrategyType.DYNAMIC_AVERAGING]
        assert len(da_cands) == 2
        assert da_cands[0].additional_details["total_legs"] == 2
        assert da_cands[0].additional_details["total_legs"] == 2

    def test_neutral_large_capacity_two_legs(self):
        # per_level_alloc = 60000/3 = 20000
        # invested = 4000, level 0, capacity = 20000 - 4000 = 16000
        # 16000 > 0.70 * 20000 = 14000, NEUTRAL → 2 legs
        entry = _base_entry(Allocated=60000, entry1=100, entry2=95, entry3=90)
        holding = _base_holding(qty=40, avg=100.0)
        config = _make_config(minimum_da_decline_pct=5.0)
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 93.0}, config=config)

        patches = _patch_ohlcv_regime("NEUTRAL")
        with patches["fetch_ohlcv"], patches["classify_regime"]:
            candidates, _ = EVALUATOR.identify_candidates(ctx)

        da_cands = [c for c in candidates if c.strategy_type == StrategyType.DYNAMIC_AVERAGING]
        assert len(da_cands) == 2

    def test_neutral_small_capacity_one_leg(self):
        # per_level_alloc = 30000/3 = 10000
        # invested = 5250, level 0, capacity = 4750
        # 4750 > 0.50 * 10000 but < 0.70 * 10000, NEUTRAL → 1 leg
        entry = _base_entry(Allocated=30000, entry1=100, entry2=95, entry3=90)
        holding = _base_holding(qty=52, avg=101.0)
        config = _make_config(minimum_da_decline_pct=5.0)
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 93.0}, config=config)

        patches = _patch_ohlcv_regime("NEUTRAL")
        with patches["fetch_ohlcv"], patches["classify_regime"]:
            candidates, _ = EVALUATOR.identify_candidates(ctx)

        da_cands = [c for c in candidates if c.strategy_type == StrategyType.DYNAMIC_AVERAGING]
        if da_cands:
            assert da_cands[0].additional_details["total_legs"] == 1


# ---------------------------------------------------------------------------
# 15. Benefit/cost guard
# ---------------------------------------------------------------------------


class TestBenefitCostGuard:
    def test_low_net_benefit_skips(self):
        # avg=105, CMP=104.5 → very small benefit
        entry = _base_entry(Allocated=30000, entry1=100, entry2=95, entry3=90)
        holding = _base_holding(qty=50, avg=105.0)
        config = _make_config(
            minimum_da_decline_pct=0.0,
            min_da_cost_pct=5.0,  # 5% cost → high
            min_da_net_benefit=100.0,
        )
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 104.5}, config=config)

        patches = _patch_ohlcv_regime("NEUTRAL", atr=0.5, atr_pct=0.5)
        with patches["fetch_ohlcv"], patches["classify_regime"]:
            candidates, skipped = EVALUATOR.identify_candidates(ctx)

        da_skipped = [s for s in skipped if s.strategy_type == StrategyType.DYNAMIC_AVERAGING]
        low_benefit = [
            s for s in da_skipped if s.reason_code == ReasonCode.LOW_PROFIT_OPPORTUNITY
        ]
        assert len(low_benefit) == 1


# ---------------------------------------------------------------------------
# 16. Trigger always above CMP
# ---------------------------------------------------------------------------


class TestTriggerAlwaysAboveCMP:
    def test_trigger_greater_than_cmp(self):
        entry = _base_entry(Allocated=30000, entry1=100, entry2=95, entry3=90)
        holding = _base_holding(qty=50, avg=105.0)
        config = _make_config(minimum_da_decline_pct=5.0)
        cmp = 93.0
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": cmp}, config=config)

        for regime in ("REVERSAL_LIKELY", "NEUTRAL", "STILL_FALLING"):
            patches = _patch_ohlcv_regime(regime)
            with patches["fetch_ohlcv"], patches["classify_regime"]:
                candidates, _ = EVALUATOR.identify_candidates(ctx)

            da_cands = [c for c in candidates if c.strategy_type == StrategyType.DYNAMIC_AVERAGING]
            for c in da_cands:
                assert c.trigger_price > c.cmp, (
                    f"Trigger {c.trigger_price} must be > CMP {c.cmp} for regime {regime}"
                )


# ---------------------------------------------------------------------------
# 17. Dynamic offset computation unit tests
# ---------------------------------------------------------------------------


class TestDynamicOffsetComputation:
    def test_base_offsets_by_regime(self):
        _, adj = _compute_dynamic_offset(
            "REVERSAL_LIKELY", drop_from_avg_pct=7.0, atr=3.0, atr_pct=3.0,
            recent_candles=[], cmp_price=93.0, support_price=None,
            support_held=False, support_broken=False,
        )
        assert adj == 0.0  # no adjustments for 7% drop, 3% ATR, no candles

    def test_delta_drop_3_5_increases_offset(self):
        final, _ = _compute_dynamic_offset(
            "NEUTRAL", drop_from_avg_pct=4.0, atr=3.0, atr_pct=3.0,
            recent_candles=[], cmp_price=93.0, support_price=None,
            support_held=False, support_broken=False,
        )
        assert final > 1.5  # base 1.5 + 0.50 adjustment

    def test_delta_drop_10_15_decreases_offset(self):
        final, _ = _compute_dynamic_offset(
            "NEUTRAL", drop_from_avg_pct=12.0, atr=3.0, atr_pct=3.0,
            recent_candles=[], cmp_price=93.0, support_price=None,
            support_held=False, support_broken=False,
        )
        assert final < 1.5  # base 1.5 - 0.25 adjustment

    def test_delta_drop_15_plus_decreases_offset_more(self):
        final, _ = _compute_dynamic_offset(
            "NEUTRAL", drop_from_avg_pct=18.0, atr=3.0, atr_pct=3.0,
            recent_candles=[], cmp_price=93.0, support_price=None,
            support_held=False, support_broken=False,
        )
        assert final < 1.25  # base 1.5 - 0.50 adjustment

    def test_high_atr_increases_offset(self):
        final, _ = _compute_dynamic_offset(
            "NEUTRAL", drop_from_avg_pct=7.0, atr=5.0, atr_pct=5.0,
            recent_candles=[], cmp_price=93.0, support_price=None,
            support_held=False, support_broken=False,
        )
        assert final >= 1.75  # base 1.5 + 0.25 ATR

    def test_low_atr_decreases_offset(self):
        final, _ = _compute_dynamic_offset(
            "NEUTRAL", drop_from_avg_pct=7.0, atr=1.5, atr_pct=1.5,
            recent_candles=[], cmp_price=93.0, support_price=None,
            support_held=False, support_broken=False,
        )
        assert final <= 1.25  # base 1.5 - 0.25 ATR

    def test_support_near_reduces_offset(self):
        final, _ = _compute_dynamic_offset(
            "NEUTRAL", drop_from_avg_pct=7.0, atr=2.0, atr_pct=3.0,
            recent_candles=[], cmp_price=93.0, support_price=92.5,
            support_held=False, support_broken=False,
        )
        assert final <= 1.5  # support adjustment: -0.25

    def test_support_broken_increases_offset(self):
        final, _ = _compute_dynamic_offset(
            "NEUTRAL", drop_from_avg_pct=7.0, atr=2.0, atr_pct=3.0,
            recent_candles=[], cmp_price=93.0, support_price=95.0,
            support_held=False, support_broken=True,
        )
        assert final >= 1.5  # support broken adjustment: +0.25

    def test_offset_clamped_to_regime_bounds(self):
        # Test that extreme adjustments don't go outside regime bounds
        final, _ = _compute_dynamic_offset(
            "REVERSAL_LIKELY", drop_from_avg_pct=3.0, atr=5.0, atr_pct=5.0,
            recent_candles=[], cmp_price=93.0, support_price=95.0,
            support_held=False, support_broken=True,
        )
        assert 0.75 <= final <= 1.50

        final, _ = _compute_dynamic_offset(
            "STILL_FALLING", drop_from_avg_pct=18.0, atr=1.5, atr_pct=1.0,
            recent_candles=[], cmp_price=93.0, support_price=92.5,
            support_held=False, support_broken=False,
        )
        assert 1.50 <= final <= 3.00


# ---------------------------------------------------------------------------
# 18. Ensure trigger above CMP helper
# ---------------------------------------------------------------------------


class TestEnsureTriggerAboveCMP:
    def test_already_above(self):
        result = _ensure_trigger_above_cmp(95.0, 93.0, 2.0, 0.1)
        assert result == 95.0

    def test_corrected_when_below(self):
        result = _ensure_trigger_above_cmp(92.0, 93.0, 2.0, 0.1)
        assert result > 93.0

    def test_corrected_at_equal(self):
        result = _ensure_trigger_above_cmp(93.0, 93.0, 2.0, 0.1)
        assert result > 93.0
