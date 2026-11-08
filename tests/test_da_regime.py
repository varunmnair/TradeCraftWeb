"""Tests for core/da_regime.py — regime classification module."""

from __future__ import annotations

from core.da_regime import RegimeResult, classify_regime


def _make_candles(
    closes: list[float],
    *,
    volume: int = 100000,
    trend_open_close: str = "down",
) -> list[dict]:
    """Build OHLCV candles from a list of close prices."""
    candles = []
    for i, close in enumerate(closes):
        if trend_open_close == "down":
            o = close * 1.002
        elif trend_open_close == "up":
            o = close * 0.998
        else:
            o = close
        candles.append({
            "date": f"2025-01-{i + 1:02d}",
            "open": o,
            "high": max(o, close) * 1.003,
            "low": min(o, close) * 0.997,
            "close": close,
            "volume": volume,
        })
    return candles


class TestEmptyAndShortData:
    def test_empty_candles_returns_neutral(self):
        result = classify_regime([])
        assert result.regime == "NEUTRAL"
        assert result.reversal_score == 0
        assert result.falling_score == 0

    def test_four_candles_returns_neutral(self):
        candles = _make_candles([100, 99, 98, 97])
        result = classify_regime(candles)
        assert result.regime == "NEUTRAL"

    def test_exactly_five_candles_classifies(self):
        candles = _make_candles([100, 99, 98, 97, 96])
        result = classify_regime(candles)
        assert result.regime in ("NEUTRAL", "STILL_FALLING", "REVERSAL_LIKELY")


class TestReversalLikely:
    def test_uptrend_classifies_as_reversal(self):
        closes = [100, 95, 90, 88, 86, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99]
        candles = _make_candles(closes, trend_open_close="up")
        result = classify_regime(candles, ema_fast_period=5, ema_slow_period=10)
        assert result.regime == "REVERSAL_LIKELY"
        assert result.reversal_score > result.falling_score

    def test_higher_lows_boost_reversal(self):
        closes = [100, 95, 92, 90, 89, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102]
        candles = _make_candles(closes, trend_open_close="up")
        result = classify_regime(candles, ema_fast_period=5, ema_slow_period=10)
        assert result.reversal_score >= 4


class TestStillFalling:
    def test_downtrend_classifies_as_still_falling(self):
        closes = [120, 118, 115, 112, 110, 108, 105, 102, 100, 98, 95, 92, 90, 88, 85, 82, 80, 78, 75, 72]
        candles = _make_candles(closes, trend_open_close="down")
        result = classify_regime(candles, ema_fast_period=5, ema_slow_period=10)
        assert result.regime == "STILL_FALLING"
        assert result.falling_score > result.reversal_score

    def test_consecutive_lower_closes_boost_falling(self):
        closes = [100, 98, 96, 94, 92, 90, 88, 86, 84, 82, 80, 78, 76, 74, 72, 70, 68, 66, 64, 62]
        candles = _make_candles(closes, trend_open_close="down")
        result = classify_regime(candles, ema_fast_period=5, ema_slow_period=10)
        assert result.falling_score >= 5


class TestNeutral:
    def test_sideways_classifies_as_neutral_or_reversal(self):
        closes = [100, 101, 99, 100, 101, 99, 100, 101, 99, 100, 101, 99, 100, 101, 99, 100, 101, 99, 100, 101]
        candles = _make_candles(closes, trend_open_close="neutral")
        result = classify_regime(candles, ema_fast_period=5, ema_slow_period=10)
        # Sideways data should NOT be classified as STILL_FALLING
        assert result.regime != "STILL_FALLING"


class TestATRCalculation:
    def test_atr_positive(self):
        candles = _make_candles([100, 99, 98, 97, 96, 95, 94, 93, 92, 91])
        result = classify_regime(candles)
        assert result.atr > 0

    def test_atr_pct_positive(self):
        candles = _make_candles([100, 99, 98, 97, 96, 95, 94, 93, 92, 91])
        result = classify_regime(candles)
        assert result.atr_pct > 0

    def test_higher_volatility_higher_atr(self):
        low_vol = _make_candles([100, 99.5, 99, 98.5, 98, 97.5, 97, 96.5, 96, 95.5])
        high_vol = _make_candles([100, 97, 94, 91, 88, 85, 82, 79, 76, 73])
        r_low = classify_regime(low_vol)
        r_high = classify_regime(high_vol)
        assert r_high.atr > r_low.atr


class TestLookbackDays:
    def test_lookback_truncates_analysis(self):
        closes = [120] * 15 + [118, 116, 114, 112, 110]
        candles = _make_candles(closes)
        r_short = classify_regime(candles, lookback_days=5)
        r_long = classify_regime(candles, lookback_days=20)
        assert r_short.regime != "NEUTRAL" or r_long.regime != "NEUTRAL"


class TestScoresNonNegative:
    def test_scores_always_non_negative(self):
        closes = [100, 95, 90, 85, 80, 75, 70, 65, 60, 55]
        candles = _make_candles(closes)
        result = classify_regime(candles)
        assert result.reversal_score >= 0
        assert result.falling_score >= 0

    def test_empty_scores_zero(self):
        result = classify_regime([])
        assert result.reversal_score == 0
        assert result.falling_score == 0
