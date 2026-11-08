"""Tests for core/services/range_analysis.py."""

from __future__ import annotations

from datetime import date, timedelta

from core.services.range_analysis import compute_range_analysis


def _candle(o: float, h: float, l: float, c: float, v: int = 100000, day_offset: int = 0) -> dict:
    return {
        "trade_date": date.today() - timedelta(days=day_offset),
        "open": o, "high": h, "low": l, "close": c, "volume": v,
    }


def _make_range_candles() -> list[dict]:
    """10 candles in a tight range 495-505 with clear support/resistance."""
    return [
        _candle(498, 505, 495, 500, day_offset=9),
        _candle(500, 503, 497, 502, day_offset=8),
        _candle(497, 500, 495, 498, day_offset=7),
        _candle(502, 505, 499, 504, day_offset=6),
        _candle(499, 502, 496, 500, day_offset=5),
        _candle(501, 504, 498, 502, day_offset=4),
        _candle(496, 499, 495, 497, day_offset=3),
        _candle(503, 505, 501, 504, day_offset=2),
        _candle(498, 501, 496, 500, day_offset=1),
        _candle(500, 503, 497, 502, day_offset=0),
    ]


def _make_trending_candles() -> list[dict]:
    """10 candles in a strong uptrend, not range-bound."""
    return [
        _candle(100, 102, 99, 101, day_offset=9),
        _candle(101, 103, 100, 102, day_offset=8),
        _candle(102, 105, 101, 104, day_offset=7),
        _candle(104, 107, 103, 106, day_offset=6),
        _candle(106, 109, 105, 108, day_offset=5),
        _candle(108, 111, 107, 110, day_offset=4),
        _candle(110, 113, 109, 112, day_offset=3),
        _candle(112, 115, 111, 114, day_offset=2),
        _candle(114, 117, 113, 116, day_offset=1),
        _candle(116, 119, 115, 118, day_offset=0),
    ]


def test_range_bound_detected():
    result = compute_range_analysis(_make_range_candles())
    assert result["is_range_bound"] is True


def test_trending_not_range_bound():
    result = compute_range_analysis(_make_trending_candles())
    assert result["is_range_bound"] is False


def test_insufficient_data():
    candles = [_candle(100, 101, 99, 100, day_offset=0)]
    result = compute_range_analysis(candles)
    assert result["is_range_bound"] is False
    assert result["range_high"] is None


def test_range_high_and_low_populated():
    candles = _make_range_candles()
    result = compute_range_analysis(candles)
    assert result["range_high"] is not None
    assert result["range_low"] is not None
    assert result["range_high"] >= result["range_low"]


def test_range_width_reasonable():
    candles = _make_range_candles()
    result = compute_range_analysis(candles)
    assert result["range_width"] is not None
    assert 0 < result["range_width"] < 20


def test_touch_counts_non_negative():
    candles = _make_range_candles()
    result = compute_range_analysis(candles)
    assert result["support_touches"] >= 0
    assert result["resistance_touches"] >= 0
    assert result["touch_count"] == result["support_touches"] + result["resistance_touches"]


def test_volume_averaged():
    candles = _make_range_candles()
    result = compute_range_analysis(candles)
    assert result["avg_volume"] is not None
    assert result["avg_volume"] == 100000.0


def test_zero_volume_handled():
    candles = [_candle(100, 102, 98, 101, v=0) for _ in range(10)]
    result = compute_range_analysis(candles)
    assert result["avg_volume"] == 0
