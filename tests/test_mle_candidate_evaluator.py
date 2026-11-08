"""Tests for core/evaluators/multi_level.py — MLE candidate evaluator."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from core.candidates import CandidateStatus, ReasonCode, StrategyType
from core.evaluators import CandidateContext, tranche_completion_threshold
from core.evaluators.multi_level import MultiLevelCandidateEvaluator
from core.strategy_config import StrategyConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cmp_manager(prices: dict[str, float] | None = None) -> MagicMock:
    mgr = MagicMock()
    mgr.get_cmp = MagicMock(side_effect=lambda ex, sym: (prices or {}).get(sym))
    return mgr


def _make_context(
    entry_levels: list[dict],
    holdings: list[dict],
    cmp_prices: dict[str, float] | None = None,
    completed_trades: set[str] | None = None,
    gtt_cache: list[dict] | None = None,
    existing_gtt: set[str] | None = None,
    config: StrategyConfig | None = None,
) -> CandidateContext:
    return CandidateContext(
        entry_levels=entry_levels,
        holdings=holdings,
        cmp_manager=_make_cmp_manager(cmp_prices or {}),
        broker=MagicMock(),
        gtt_cache=gtt_cache or [],
        completed_trade_symbols=completed_trades or set(),
        config=config or StrategyConfig(),
        existing_gtt_symbols=existing_gtt or set(),
    )


def _base_entry(symbol: str = "TEST", **overrides) -> dict:
    entry = {
        "symbol": symbol,
        "Allocated": 30000,
        "exchange": "NSE",
        "entry1": 150.0,
        "entry2": 145.0,
        "entry3": 140.0,
        "quality": "A",
        "thesis_break_price": None,
    }
    entry.update(overrides)
    return entry


def _base_holding(symbol: str = "TEST", qty: int = 0, avg: float = 0.0) -> dict:
    return {
        "tradingsymbol": symbol,
        "quantity": qty,
        "t1_quantity": 0,
        "average_price": avg,
        "exchange": "NSE",
    }


EVALUATOR = MultiLevelCandidateEvaluator()


# ---------------------------------------------------------------------------
# 1. Tranche completion threshold: invested=9696, per_level=10000
#    E1 gap=304 <= threshold=800 → E1 effectively complete → E2 candidate
# ---------------------------------------------------------------------------


class TestTrancheCompletionThreshold:
    def test_e1_near_complete_advances_to_e2(self):
        """invested=9696, gap=304, threshold=800 → E1 complete, next=E2."""
        entry = _base_entry(Allocated=30000, entry1=150, entry2=145, entry3=140)
        # invested = qty * avg = 64 * 151.50 = 9696
        holding = _base_holding(qty=64, avg=151.50)
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 150.0})

        candidates, skipped = EVALUATOR.identify_candidates(ctx)
        mle = [c for c in candidates if c.strategy_type == StrategyType.MULTI_LEVEL]

        # threshold = max(10000 * 0.08, 150) = max(800, 150) = 800
        # E1 target = 10000, gap = 10000 - 9696 = 304 <= 800 → E1 complete
        # Next tranche = E2 (index 1)
        assert len(mle) == 1
        assert mle[0].signal == "E2"

    def test_e2_near_complete_advances_to_e3(self):
        """invested=19600, gap=400, threshold=800 → E2 complete, next=E3."""
        entry = _base_entry(Allocated=30000, entry1=150, entry2=145, entry3=140)
        # invested = 19600
        holding = _base_holding(qty=130, avg=150.77)  # ~19600
        # Override to exact invested amount via allocated calc
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 150.0})

        # Manually set invested to 19600 by adjusting holding
        # qty=130, avg=150.77 → invested = 19600.1
        candidates, skipped = EVALUATOR.identify_candidates(ctx)
        mle = [c for c in candidates if c.strategy_type == StrategyType.MULTI_LEVEL]

        # threshold = max(800, 150) = 800
        # E2 target = 20000, gap = 20000 - 19600 = 400 <= 800 → E2 complete
        # Next tranche = E3 (index 2)
        assert len(mle) == 1
        assert mle[0].signal == "E3"

    def test_high_cmp_threshold_use_cmp(self):
        """CMP=2000, invested=8500 → threshold=2000, gap=1500 → E1 complete."""
        # E3 is set low enough that CMP=2000 doesn't trigger price-too-far-below-E3
        entry = _base_entry(Allocated=30000, entry1=2500, entry2=2400, entry3=2000)
        holding = _base_holding(qty=3, avg=2833.33)  # invested = 8500
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 2000.0})

        candidates, skipped = EVALUATOR.identify_candidates(ctx)
        mle = [c for c in candidates if c.strategy_type == StrategyType.MULTI_LEVEL]

        # per_level = 10000, threshold = max(800, 2000) = 2000
        # E1 target = 10000, gap = 1500 <= 2000 → E1 complete
        # Next tranche = E2
        assert len(mle) == 1
        assert mle[0].signal == "E2"

    def test_mid_tranche_invested_suppresses_mle(self):
        """invested=9100 is between the ₹0 and ₹10k boundaries → MLE suppressed, DA owns."""
        entry = _base_entry(Allocated=30000, entry1=150, entry2=145, entry3=140)
        holding = _base_holding(qty=60, avg=151.67)  # invested ~ 9100
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 150.0})

        candidates, skipped = EVALUATOR.identify_candidates(ctx)
        mle = [c for c in candidates if c.strategy_type == StrategyType.MULTI_LEVEL]
        mid_tranche = [s for s in skipped if s.reason_code == ReasonCode.HOLDING_BETWEEN_LEVELS]

        # threshold = max(800, 150) = 800
        # E1 boundary = ₹0, |9100 - 0| = 9100 > 800 → not parked at a boundary → MLE suppressed
        assert len(mle) == 0
        assert len(mid_tranche) == 1

    def test_at_tranche_boundary_generates_next_level(self):
        """BEL-style: invested=20000 (E2 boundary) → E3 candidate fires."""
        entry = _base_entry(Allocated=30000, entry1=386.5, entry2=375.0, entry3=369.0)
        holding = _base_holding(qty=50, avg=400.0)  # invested = 20000
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 400.65})

        candidates, _ = EVALUATOR.identify_candidates(ctx)
        mle = [c for c in candidates if c.strategy_type == StrategyType.MULTI_LEVEL]

        assert len(mle) == 1
        assert mle[0].signal == "E3"

    def test_boundary_within_threshold_fires(self):
        """invested=20500, ₹500 above the ₹20k boundary (≤ threshold 800) → E3 fires."""
        entry = _base_entry(Allocated=30000, entry1=386.5, entry2=375.0, entry3=369.0)
        holding = _base_holding(qty=50, avg=410.0)  # invested = 20500
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 400.65})

        candidates, _ = EVALUATOR.identify_candidates(ctx)
        mle = [c for c in candidates if c.strategy_type == StrategyType.MULTI_LEVEL]

        assert len(mle) == 1
        assert mle[0].signal == "E3"

    def test_bel_style_mid_tranche_suppresses_mle(self):
        """BEL case: invested ~25572 sits between ₹20k and ₹30k → no MLE, DA only."""
        entry = _base_entry(Allocated=30000, entry1=386.5, entry2=375.0, entry3=369.0)
        holding = _base_holding(qty=64, avg=399.56)  # invested = 25571.84
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 400.65})

        candidates, skipped = EVALUATOR.identify_candidates(ctx)
        mle = [c for c in candidates if c.strategy_type == StrategyType.MULTI_LEVEL]
        mid_tranche = [s for s in skipped if s.reason_code == ReasonCode.HOLDING_BETWEEN_LEVELS]

        # threshold = max(800, 400.65) = 800; boundary = ₹20k; |25572 - 20000| > 800
        assert len(mle) == 0
        assert len(mid_tranche) == 1

    def test_zero_invested_starts_at_e1(self):
        """No holding → invested=0 → next tranche = E1."""
        entry = _base_entry(Allocated=30000, entry1=150, entry2=145, entry3=140)
        ctx = _make_context([entry], [], cmp_prices={"TEST": 150.0})

        candidates, skipped = EVALUATOR.identify_candidates(ctx)
        mle = [c for c in candidates if c.strategy_type == StrategyType.MULTI_LEVEL]

        assert len(mle) == 1
        assert mle[0].signal == "E1"

    def test_fully_invested_skips(self):
        """invested >= allocated → ALLOCATION_COMPLETE."""
        entry = _base_entry(Allocated=30000, entry1=150, entry2=145, entry3=140)
        holding = _base_holding(qty=200, avg=150.0)  # invested = 30000
        ctx = _make_context([entry], [holding], cmp_prices={"TEST": 150.0})

        candidates, skipped = EVALUATOR.identify_candidates(ctx)
        mle = [c for c in candidates if c.strategy_type == StrategyType.MULTI_LEVEL]
        alloc_complete = [s for s in skipped if s.reason_code == ReasonCode.ALLOCATION_COMPLETE]

        assert len(mle) == 0
        assert len(alloc_complete) >= 1


# ---------------------------------------------------------------------------
# 2. Entry level order validation
# ---------------------------------------------------------------------------


class TestEntryLevelOrderValidation:
    def test_invalid_order_e3_higher_than_e2(self):
        """E1=88.50, E2=85.00, E3=88.00 → INVALID_ENTRY_LEVEL_ORDER."""
        entry = _base_entry(
            Allocated=30000,
            entry1=88.50,
            entry2=85.00,
            entry3=88.00,  # E3 > E2, invalid
        )
        ctx = _make_context([entry], [], cmp_prices={"TEST": 87.0})

        candidates, skipped = EVALUATOR.identify_candidates(ctx)
        mle = [c for c in candidates if c.strategy_type == StrategyType.MULTI_LEVEL]
        invalid_order = [
            s for s in skipped if s.reason_code == ReasonCode.INVALID_ENTRY_LEVEL_ORDER
        ]

        assert len(mle) == 0
        assert len(invalid_order) == 1

    def test_invalid_order_equal_prices(self):
        """E1=100, E2=100, E3=95 → INVALID_ENTRY_LEVEL_ORDER (E1 not > E2)."""
        entry = _base_entry(
            Allocated=30000,
            entry1=100.0,
            entry2=100.0,  # equal to E1, invalid
            entry3=95.0,
        )
        ctx = _make_context([entry], [], cmp_prices={"TEST": 98.0})

        candidates, skipped = EVALUATOR.identify_candidates(ctx)
        invalid_order = [
            s for s in skipped if s.reason_code == ReasonCode.INVALID_ENTRY_LEVEL_ORDER
        ]

        assert len(invalid_order) == 1

    def test_invalid_order_e2_higher_than_e1(self):
        """E1=100, E2=105, E3=95 → INVALID_ENTRY_LEVEL_ORDER."""
        entry = _base_entry(
            Allocated=30000,
            entry1=100.0,
            entry2=105.0,  # > E1, invalid
            entry3=95.0,
        )
        ctx = _make_context([entry], [], cmp_prices={"TEST": 98.0})

        candidates, skipped = EVALUATOR.identify_candidates(ctx)
        invalid_order = [
            s for s in skipped if s.reason_code == ReasonCode.INVALID_ENTRY_LEVEL_ORDER
        ]

        assert len(invalid_order) == 1

    def test_valid_order_passes(self):
        """E1=150, E2=145, E3=140 → valid, no INVALID_ENTRY_LEVEL_ORDER skip."""
        entry = _base_entry(Allocated=30000, entry1=150, entry2=145, entry3=140)
        ctx = _make_context([entry], [], cmp_prices={"TEST": 150.0})

        _, skipped = EVALUATOR.identify_candidates(ctx)
        invalid_order = [
            s for s in skipped if s.reason_code == ReasonCode.INVALID_ENTRY_LEVEL_ORDER
        ]

        assert len(invalid_order) == 0

    def test_valid_partial_entries_pass(self):
        """E1=150, E2=null, E3=null → valid (single entry)."""
        entry = _base_entry(Allocated=30000, entry1=150, entry2=None, entry3=None)
        ctx = _make_context([entry], [], cmp_prices={"TEST": 150.0})

        _, skipped = EVALUATOR.identify_candidates(ctx)
        invalid_order = [
            s for s in skipped if s.reason_code == ReasonCode.INVALID_ENTRY_LEVEL_ORDER
        ]

        assert len(invalid_order) == 0


# ---------------------------------------------------------------------------
# 3. ₹1 entry level: no special handling, skipped via opportunity window
# ---------------------------------------------------------------------------


class TestRupeeOneEntryLevel:
    def test_entry1_eq_1_cmp_500_skipped_via_opportunity_window(self):
        """E1=1, CMP=500 → PRICE_ABOVE_OPPORTUNITY_WINDOW, no special rule."""
        entry = _base_entry(Allocated=30000, entry1=1.0, entry2=None, entry3=None)
        ctx = _make_context([entry], [], cmp_prices={"TEST": 500.0})

        _, skipped = EVALUATOR.identify_candidates(ctx)
        opp_window = [
            s for s in skipped if s.reason_code == ReasonCode.PRICE_ABOVE_OPPORTUNITY_WINDOW
        ]
        invalid_order = [
            s for s in skipped if s.reason_code == ReasonCode.INVALID_ENTRY_LEVEL_ORDER
        ]

        assert len(opp_window) == 1
        assert len(invalid_order) == 0  # no special ₹1 validation


# ---------------------------------------------------------------------------
# 4. Amount = actual order value (qty * order_price)
# ---------------------------------------------------------------------------


class TestAmountIsActualOrderValue:
    def test_amount_equals_qty_times_order_price(self):
        """Amount field should be qty * order_price, not the tranche target delta."""
        entry = _base_entry(Allocated=30000, entry1=150, entry2=145, entry3=140)
        ctx = _make_context([entry], [], cmp_prices={"TEST": 150.0})

        candidates, _ = EVALUATOR.identify_candidates(ctx)
        mle = [c for c in candidates if c.strategy_type == StrategyType.MULTI_LEVEL]
        assert len(mle) == 1

        c = mle[0]
        expected_amount = round(c.qty * c.order_price, 2)
        assert c.amount == expected_amount


# ---------------------------------------------------------------------------
# 5. Opportunity window: CMP within window of tranche price passes
# ---------------------------------------------------------------------------


class TestOpportunityWindow:
    def test_cmp_at_entry_price_passes(self):
        """CMP = E1 price → within window → E1 candidate generated."""
        entry = _base_entry(Allocated=30000, entry1=150, entry2=145, entry3=140)
        ctx = _make_context([entry], [], cmp_prices={"TEST": 150.0})

        candidates, _ = EVALUATOR.identify_candidates(ctx)
        mle = [c for c in candidates if c.strategy_type == StrategyType.MULTI_LEVEL]
        assert len(mle) == 1
        assert mle[0].signal == "E1"

    def test_cmp_above_entry_within_window_passes(self):
        """CMP = 160, E1 = 150 → 6.7% above, within 10% window → passes."""
        entry = _base_entry(Allocated=30000, entry1=150, entry2=145, entry3=140)
        ctx = _make_context([entry], [], cmp_prices={"TEST": 160.0})

        candidates, _ = EVALUATOR.identify_candidates(ctx)
        mle = [c for c in candidates if c.strategy_type == StrategyType.MULTI_LEVEL]
        assert len(mle) == 1

    def test_cmp_above_window_skips(self):
        """CMP = 170, E1 = 150 → 13.3% above, > 10% window → PRICE_ABOVE_OPPORTUNITY_WINDOW."""
        entry = _base_entry(Allocated=30000, entry1=150, entry2=145, entry3=140)
        ctx = _make_context([entry], [], cmp_prices={"TEST": 170.0})

        _, skipped = EVALUATOR.identify_candidates(ctx)
        opp_skips = [
            s for s in skipped if s.reason_code == ReasonCode.PRICE_ABOVE_OPPORTUNITY_WINDOW
        ]
        assert len(opp_skips) == 1


# ---------------------------------------------------------------------------
# 6. Threshold helper unit test
# ---------------------------------------------------------------------------


class TestTrancheCompletionThresholdHelper:
    def test_threshold_uses_8_percent_when_cmp_is_low(self):
        """per_level=10000, CMP=150 → threshold = max(800, 150) = 800."""
        assert tranche_completion_threshold(10000, 150) == 800

    def test_threshold_uses_cmp_when_cmp_is_high(self):
        """per_level=10000, CMP=2000 → threshold = max(800, 2000) = 2000."""
        assert tranche_completion_threshold(10000, 2000) == 2000

    def test_threshold_at_boundary(self):
        """per_level=10000, CMP=800 → threshold = max(800, 800) = 800."""
        assert tranche_completion_threshold(10000, 800) == 800

    def test_threshold_small_allocation(self):
        """per_level=5000, CMP=100 → threshold = max(400, 100) = 400."""
        assert tranche_completion_threshold(5000, 100) == 400
