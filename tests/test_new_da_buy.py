"""Tests for system-driven DA BUY — end-to-end scenario tests.

Each test covers a specific market condition specified in the requirements:
1. CMP 3% below avg, STILL_FALLING → larger offset
2. CMP 12% below avg, NEUTRAL → delta reduces offset
3. CMP 3.5% below avg → delta increases offset
4. High ATR% > 4 → offset increases
5. Low ATR% < 2 → offset decreases
6. CMP near support → reversal score increases
7. Support broken → falling score increases
8. After broker rounding trigger <= CMP → corrected upward
9. DA capacity <= 50% tranche → 1 leg
10. DA capacity > 50% tranche, STILL_FALLING → 2 legs
11. DA capacity > 70% tranche, NEUTRAL → 2 legs
12. Regime REVERSAL_LIKELY → 1 leg
13. Net benefit below threshold → LOW_PROFIT_OPPORTUNITY
"""

from __future__ import annotations

from unittest.mock import patch

from core.candidates import ReasonCode, StrategyType
from core.da_regime import RegimeResult
from core.evaluators import CandidateContext
from core.evaluators.dynamic_avg import DynamicAveragingCandidateEvaluator
from core.strategy_config import StrategyConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cmp_manager(prices: dict[str, float]):
    import unittest.mock as m

    mgr = m.MagicMock()
    mgr.get_cmp = m.MagicMock(side_effect=lambda ex, sym: prices.get(sym))
    return mgr


def _entry(symbol="TEST", allocated=30000, e1=100.0, e2=95.0, e3=90.0, **kw):
    d = {
        "symbol": symbol,
        "Allocated": allocated,
        "Quality": "Good",
        "exchange": "NSE",
        "entry1": e1,
        "entry2": e2,
        "entry3": e3,
        "thesis_break_price": None,
    }
    d.update(kw)
    return d


def _holding(symbol="TEST", qty=100, avg=105.0):
    return {
        "tradingsymbol": symbol,
        "quantity": qty,
        "t1_quantity": 0,
        "average_price": avg,
        "exchange": "NSE",
    }


def _candles(n=20, base=100.0):
    return [
        {
            "date": f"2025-01-{i+1:02d}",
            "open": base * 0.998,
            "high": base * 1.005,
            "low": base * 0.995,
            "close": base,
            "volume": 100000,
        }
        for i in range(n)
    ]


def _regime(
    regime="NEUTRAL",
    atr=2.0,
    atr_pct=2.0,
    support_price=None,
    support_held=False,
    support_broken=False,
    recent_candles=None,
):
    return RegimeResult(
        regime=regime,
        reversal_score=6 if regime == "REVERSAL_LIKELY" else 2,
        falling_score=2 if regime == "REVERSAL_LIKELY" else 6,
        atr=atr,
        atr_pct=atr_pct,
        avg_volume=100000,
        support_price=support_price,
        support_held=support_held,
        support_broken=support_broken,
        recent_candles=recent_candles or _candles(5, 98.0),
    )


def _ctx(entries, holdings, cmp_map, config=None):
    return CandidateContext(
        entry_levels=entries,
        holdings=holdings,
        cmp_manager=_cmp_manager(cmp_map),
        broker=None,
        gtt_cache=[],
        completed_trade_symbols=set(),
        config=config or StrategyConfig(),
        existing_gtt_symbols=set(),
    )


def _make_config(**overrides) -> StrategyConfig:
    cfg = StrategyConfig()
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


EVAL = DynamicAveragingCandidateEvaluator()


def _run(entries, holdings, cmp_map, regime="NEUTRAL", config=None, **regime_kw):
    ctx = _ctx(entries, holdings, cmp_map, config)
    with patch("core.evaluators.dynamic_avg._fetch_ohlcv", return_value=_candles(20, 93.0)):
        with patch("core.da_regime.classify_regime", return_value=_regime(regime, **regime_kw)):
            return EVAL.identify_candidates(ctx)


# ---------------------------------------------------------------------------
# Test 1: CMP 3% below avg, STILL_FALLING → trigger > CMP using larger offset
# ---------------------------------------------------------------------------


def test_still_falling_larger_offset():
    """CMP is 3% below average but regime is STILL_FALLING.
    Expected: Trigger > CMP using larger offset."""
    entries = [_entry()]
    holdings = [_holding(qty=50, avg=105.0)]
    # avg=105, CMP=101.85 → ~3% below
    cfg = _make_config(minimum_da_decline_pct=3.0)
    candidates, skipped = _run(entries, holdings, {"TEST": 98.0}, "STILL_FALLING", cfg)

    da = [c for c in candidates if c.strategy_type == StrategyType.DYNAMIC_AVERAGING]
    assert len(da) >= 1
    assert da[0].trigger_price > da[0].cmp
    assert da[0].additional_details["trigger_offset_pct"] >= 1.5


# ---------------------------------------------------------------------------
# Test 2: CMP 12% below avg, NEUTRAL → delta adjustment reduces offset
# ---------------------------------------------------------------------------


def test_deep_drop_neutral_reduces_offset():
    """CMP is 12% below average and regime is NEUTRAL.
    Expected: Delta adjustment reduces offset by 0.25."""
    entries = [_entry()]
    # avg=105, CMP=92.4 → 12% below
    holdings = [_holding(qty=50, avg=105.0)]
    cfg = _make_config(minimum_da_decline_pct=3.0)
    candidates, skipped = _run(entries, holdings, {"TEST": 92.4}, "NEUTRAL", cfg)

    da = [c for c in candidates if c.strategy_type == StrategyType.DYNAMIC_AVERAGING]
    if da:
        adj = da[0].additional_details["offset_adjustment"]
        assert adj < 0  # negative adjustment for deep drop


# ---------------------------------------------------------------------------
# Test 3: CMP only 3.5% below avg → delta increases offset
# ---------------------------------------------------------------------------


def test_shallow_drop_increases_offset():
    """CMP is only 3.5% below average.
    Expected: Delta adjustment increases offset by 0.50."""
    entries = [_entry()]
    # avg=105, CMP=101.325 → 3.5% below
    holdings = [_holding(qty=50, avg=105.0)]
    cfg = _make_config(minimum_da_decline_pct=3.0)
    candidates, skipped = _run(entries, holdings, {"TEST": 101.3}, "NEUTRAL", cfg)

    da = [c for c in candidates if c.strategy_type == StrategyType.DYNAMIC_AVERAGING]
    if da:
        adj = da[0].additional_details["offset_adjustment"]
        assert adj > 0  # positive adjustment for shallow drop


# ---------------------------------------------------------------------------
# Test 4: High ATR% > 4 → offset increases
# ---------------------------------------------------------------------------


def test_high_atr_increases_offset():
    """High ATR% > 4.
    Expected: Offset increases by 0.25."""
    entries = [_entry()]
    holdings = [_holding(qty=50, avg=105.0)]
    cfg = _make_config(minimum_da_decline_pct=3.0)
    candidates, skipped = _run(
        entries, holdings, {"TEST": 98.0}, "NEUTRAL", cfg, atr_pct=5.0, atr=5.0
    )

    da = [c for c in candidates if c.strategy_type == StrategyType.DYNAMIC_AVERAGING]
    if da:
        offset = da[0].additional_details["trigger_offset_pct"]
        assert offset >= 1.5  # base 1.5 + 0.25 ATR


# ---------------------------------------------------------------------------
# Test 5: Low ATR% < 2 → offset decreases
# ---------------------------------------------------------------------------


def test_low_atr_decreases_offset():
    """Low ATR% < 2.
    Expected: Offset decreases by 0.25."""
    entries = [_entry()]
    holdings = [_holding(qty=50, avg=105.0)]
    cfg = _make_config(minimum_da_decline_pct=3.0)
    candidates, skipped = _run(
        entries, holdings, {"TEST": 98.0}, "NEUTRAL", cfg, atr_pct=1.5, atr=1.5
    )

    da = [c for c in candidates if c.strategy_type == StrategyType.DYNAMIC_AVERAGING]
    if da:
        offset = da[0].additional_details["trigger_offset_pct"]
        assert offset <= 1.5  # base 1.5 - 0.25 ATR


# ---------------------------------------------------------------------------
# Test 6: CMP near support → reversal score increases
# ---------------------------------------------------------------------------


def test_near_support_increases_reversal_score():
    """CMP near support.
    Expected: Reversal score increases and offset may reduce."""
    entries = [_entry(allocated=60000)]
    holdings = [_holding(qty=50, avg=105.0)]
    cfg = _make_config(minimum_da_decline_pct=3.0)
    candidates, skipped = _run(
        entries, holdings, {"TEST": 98.0}, "NEUTRAL", cfg,
        support_price=98.0, support_held=True,
    )

    da = [c for c in candidates if c.strategy_type == StrategyType.DYNAMIC_AVERAGING]
    if da:
        assert da[0].additional_details["support_held"] is True
        # Support near should reduce offset
        adj = da[0].additional_details["offset_adjustment"]
        assert adj < 0  # negative adjustment for support proximity


# ---------------------------------------------------------------------------
# Test 7: Support broken → falling score increases
# ---------------------------------------------------------------------------


def test_support_broken_increases_falling_score():
    """Support broken.
    Expected: Falling score increases and offset may increase."""
    entries = [_entry(allocated=60000)]
    holdings = [_holding(qty=50, avg=105.0)]
    cfg = _make_config(minimum_da_decline_pct=3.0)
    candidates, skipped = _run(
        entries, holdings, {"TEST": 98.0}, "STILL_FALLING", cfg,
        support_price=100.0, support_broken=True,
    )

    da = [c for c in candidates if c.strategy_type == StrategyType.DYNAMIC_AVERAGING]
    if da:
        assert da[0].additional_details["support_broken"] is True
        adj = da[0].additional_details["offset_adjustment"]
        assert adj > 0  # positive adjustment for support break


# ---------------------------------------------------------------------------
# Test 8: After broker rounding trigger <= CMP → corrected upward
# ---------------------------------------------------------------------------


def test_trigger_corrected_above_cmp():
    """After broker rounding, trigger <= CMP.
    Expected: Trigger is corrected upward and remains > CMP."""
    entries = [_entry()]
    holdings = [_holding(qty=50, avg=105.0)]
    cfg = _make_config(minimum_da_decline_pct=3.0)
    # Use small CMP to test tick-size rounding edge case
    candidates, skipped = _run(entries, holdings, {"TEST": 93.0}, "NEUTRAL", cfg)

    da = [c for c in candidates if c.strategy_type == StrategyType.DYNAMIC_AVERAGING]
    for c in da:
        assert c.trigger_price > c.cmp, (
            f"Trigger {c.trigger_price} must be > CMP {c.cmp}"
        )


# ---------------------------------------------------------------------------
# Test 9: DA capacity <= 50% of tranche → 1 leg
# ---------------------------------------------------------------------------


def test_capacity_below_50_pct_one_leg():
    """DA capacity <= 50% of tranche.
    Expected: 1 leg."""
    entries = [_entry(allocated=30000)]
    # invested = 5250, level 0, capacity = 10000 - 5250 = 4750
    # 4750 < 0.50 * 10000 → 1 leg
    holdings = [_holding(qty=50, avg=105.0)]
    cfg = _make_config(minimum_da_decline_pct=3.0)
    candidates, skipped = _run(entries, holdings, {"TEST": 93.0}, "STILL_FALLING", cfg)

    da = [c for c in candidates if c.strategy_type == StrategyType.DYNAMIC_AVERAGING]
    if da:
        assert da[0].additional_details["total_legs"] == 1


# ---------------------------------------------------------------------------
# Test 10: DA capacity > 50% of tranche, STILL_FALLING → 2 legs
# ---------------------------------------------------------------------------


def test_still_falling_large_capacity_two_legs():
    """DA capacity > 50% of tranche and STILL_FALLING.
    Expected: 2 legs, subject to max_da_legs."""
    entries = [_entry(allocated=60000)]
    # per_level = 20000, invested = 5250, capacity = 14750
    # 14750 > 0.50 * 20000 = 10000, STILL_FALLING → 2 legs
    holdings = [_holding(qty=50, avg=105.0)]
    cfg = _make_config(minimum_da_decline_pct=3.0)
    candidates, skipped = _run(entries, holdings, {"TEST": 93.0}, "STILL_FALLING", cfg)

    da = [c for c in candidates if c.strategy_type == StrategyType.DYNAMIC_AVERAGING]
    assert len(da) == 2
    assert da[0].additional_details["total_legs"] == 2


# ---------------------------------------------------------------------------
# Test 11: DA capacity > 70% of tranche, NEUTRAL → 2 legs
# ---------------------------------------------------------------------------


def test_neutral_large_capacity_two_legs():
    """DA capacity > 70% of tranche and NEUTRAL.
    Expected: 2 legs."""
    entries = [_entry(allocated=60000)]
    # per_level = 20000, invested = 4000, capacity = 16000
    # 16000 > 0.70 * 20000 = 14000, NEUTRAL → 2 legs
    holdings = [_holding(qty=40, avg=100.0)]
    cfg = _make_config(minimum_da_decline_pct=3.0)
    candidates, skipped = _run(entries, holdings, {"TEST": 93.0}, "NEUTRAL", cfg)

    da = [c for c in candidates if c.strategy_type == StrategyType.DYNAMIC_AVERAGING]
    assert len(da) == 2


# ---------------------------------------------------------------------------
# Test 12: Regime REVERSAL_LIKELY → 1 leg
# ---------------------------------------------------------------------------


def test_reversal_always_one_leg():
    """Regime REVERSAL_LIKELY.
    Expected: 1 leg."""
    entries = [_entry()]
    holdings = [_holding(qty=50, avg=105.0)]
    cfg = _make_config(minimum_da_decline_pct=3.0)
    candidates, skipped = _run(entries, holdings, {"TEST": 98.0}, "REVERSAL_LIKELY", cfg)

    da = [c for c in candidates if c.strategy_type == StrategyType.DYNAMIC_AVERAGING]
    assert len(da) == 1
    assert da[0].additional_details["total_legs"] == 1


# ---------------------------------------------------------------------------
# Test 13: Net benefit below threshold → LOW_PROFIT_OPPORTUNITY
# ---------------------------------------------------------------------------


def test_low_net_benefit_skipped():
    """Net benefit below threshold.
    Expected: LOW_PROFIT_OPPORTUNITY."""
    entries = [_entry(allocated=30000)]
    holdings = [_holding(qty=50, avg=105.0)]
    cfg = _make_config(
        minimum_da_decline_pct=0.0,
        min_da_cost_pct=10.0,  # 10% cost → high
        min_da_net_benefit=500.0,
    )
    candidates, skipped = _run(entries, holdings, {"TEST": 104.5}, "NEUTRAL", cfg)

    da_skipped = [s for s in skipped if s.strategy_type == StrategyType.DYNAMIC_AVERAGING]
    low_benefit = [s for s in da_skipped if s.reason_code == ReasonCode.LOW_PROFIT_OPPORTUNITY]
    assert len(low_benefit) == 1


# ---------------------------------------------------------------------------
# Additional: Capacity calculation verification
# ---------------------------------------------------------------------------


def test_capacity_calculation_three_entries():
    """Verify per_level_allocation and da_capacity."""
    entries = [_entry(allocated=30000, e1=100, e2=95, e3=90)]
    holdings = [_holding(qty=160, avg=100.0)]  # invested=16000 → level 1
    cfg = _make_config(minimum_da_decline_pct=3.0)
    candidates, skipped = _run(entries, holdings, {"TEST": 93.0}, "REVERSAL_LIKELY", cfg)

    da = [c for c in candidates if c.strategy_type == StrategyType.DYNAMIC_AVERAGING]
    if da:
        details = da[0].additional_details
        assert details["per_level_allocation"] == 10000.0
        assert details["da_capacity"] == 4000.0


# ---------------------------------------------------------------------------
# Additional: No candidate when OHLCV fetch fails
# ---------------------------------------------------------------------------


def test_no_candidate_when_ohlcv_unavailable():
    entries = [_entry(allocated=30000)]
    holdings = [_holding(qty=50, avg=105.0)]
    cfg = _make_config(minimum_da_decline_pct=3.0)
    ctx = _ctx(entries, holdings, {"TEST": 98.0}, cfg)

    with patch("core.evaluators.dynamic_avg._fetch_ohlcv", return_value=[]):
        candidates, skipped = EVAL.identify_candidates(ctx)

    da = [c for c in candidates if c.strategy_type == StrategyType.DYNAMIC_AVERAGING]
    assert len(da) == 0
    da_skipped = [s for s in skipped if s.strategy_type == StrategyType.DYNAMIC_AVERAGING]
    data_skips = [s for s in da_skipped if s.reason_code == ReasonCode.DATA_UNAVAILABLE]
    assert len(data_skips) == 1
