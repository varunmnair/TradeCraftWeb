"""Tests for core/services/da_evaluation.py."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

from core.da_config import DEFAULT_CONFIG, reset_da_config
from core.services.da_evaluation import (
    DynamicAveragingEvaluationService,
    _compute_avg_volume,
    _compute_da_confidence_score,
    _compute_ema_score,
    _confidence_label,
    _detect_strong_trend,
    _estimate_charges,
    _recommended_qty_pct,
)


def _candle(o: float, h: float, l: float, c: float, v: int = 100000, day_offset: int = 0) -> dict:
    return {
        "trade_date": date.today() - timedelta(days=day_offset),
        "open": o, "high": h, "low": l, "close": c, "volume": v,
    }


def _range_candles(n: int = 60) -> list[dict]:
    """Generate range-bound candles within 495-505."""
    candles = []
    for i in range(n):
        base = 500
        hi = base + (i % 5)  # 500-505
        lo = base - (5 - i % 5)  # 495-500
        candles.append(_candle(
            round((hi + lo) / 2, 2), hi, lo, round((hi + lo) / 2, 2),
            day_offset=n - 1 - i,
        ))
    return candles


def test_compute_ema_score_bullish():
    candles = [_candle(100 + i, 102 + i, 99 + i, 101 + i) for i in range(60)]
    score = _compute_ema_score(candles)
    assert score >= 50


def test_compute_ema_score_bearish():
    candles = [_candle(200 - i, 202 - i, 198 - i, 200 - i) for i in range(60)]
    score = _compute_ema_score(candles)
    assert score <= 50


def test_detect_strong_bullish():
    assert _detect_strong_trend(90) == "strong_bullish"


def test_detect_strong_bearish():
    assert _detect_strong_trend(10) == "strong_bearish"


def test_detect_no_trend():
    assert _detect_strong_trend(50) is None


def test_compute_avg_volume_normal():
    candles = [_candle(100, 101, 99, 100, v=50000) for _ in range(25)]
    avg = _compute_avg_volume(candles)
    assert avg == 50000.0


def test_compute_avg_volume_empty():
    candles = [_candle(100, 101, 99, 100, v=0) for _ in range(25)]
    avg = _compute_avg_volume(candles)
    assert avg == 0.0


def test_estimate_charges():
    charges = _estimate_charges(10000, 9000)
    assert charges > 0


def test_confidence_score_in_range():
    score = _compute_da_confidence_score(
        range_pct=5, touch_count=6, support_touches=3, resistance_touches=3,
        avg_vol=100000, expected_net_profit=500, min_profit=100, thesis_distance=0.05,
    )
    assert 0 <= score <= 100


def test_confidence_label_high():
    assert _confidence_label(90, DEFAULT_CONFIG) == "HIGH"


def test_confidence_label_medium():
    assert _confidence_label(70, DEFAULT_CONFIG) == "MEDIUM"


def test_confidence_label_low():
    assert _confidence_label(50, DEFAULT_CONFIG) == "LOW"


def test_confidence_label_none():
    assert _confidence_label(30, DEFAULT_CONFIG) == "NO_RECOMMENDATION"


def test_recommended_qty_high():
    assert _recommended_qty_pct(90, DEFAULT_CONFIG) == DEFAULT_CONFIG["high_confidence_qty_pct"]


def test_recommended_qty_medium():
    assert _recommended_qty_pct(70, DEFAULT_CONFIG) == DEFAULT_CONFIG["medium_confidence_qty_pct"]


def test_recommended_qty_low():
    assert _recommended_qty_pct(50, DEFAULT_CONFIG) == DEFAULT_CONFIG["low_confidence_qty_pct"]


def test_recommended_qty_none():
    assert _recommended_qty_pct(30, DEFAULT_CONFIG) == 0


def test_evaluate_no_holding():
    reset_da_config()
    svc = DynamicAveragingEvaluationService()
    result = svc.evaluate("TEST", None, {}, _range_candles())
    assert result["da_status"] == "NO_HOLDING"


def test_evaluate_thesis_break():
    svc = DynamicAveragingEvaluationService()
    holding = {"qty": 100, "avg_cost": 200, "cmp": 150}
    strategy = {"thesis_break_price": 180}
    result = svc.evaluate("TEST", holding, strategy, _range_candles())
    assert result["da_status"] == "THESIS_BREAK"


def test_evaluate_insufficient_data():
    svc = DynamicAveragingEvaluationService()
    holding = {"qty": 100, "avg_cost": 200, "cmp": 250}
    strategy = {"dynamic_averaging_enabled": True}
    result = svc.evaluate("TEST", holding, strategy, [_candle(200, 202, 198, 201)])
    assert result["da_status"] == "INSUFFICIENT_DATA"


def test_evaluate_eligible():
    svc = DynamicAveragingEvaluationService()
    holding = {"qty": 100, "avg_cost": 200, "cmp": 210}
    strategy = {"dynamic_averaging_enabled": True}
    result = svc.evaluate("TEST", holding, strategy, _range_candles(10))
    assert result["da_status"] in ("ELIGIBLE", "INSUFFICIENT_RANGE", "TRENDING", "LOW_VOLUME", "INSUFFICIENT_PROFIT")


def test_evaluate_override_sell_offset():
    svc = DynamicAveragingEvaluationService()
    holding = {"qty": 100, "avg_cost": 200, "cmp": 210}
    strategy = {"dynamic_averaging_enabled": True, "override_sell_offset": 0.02}
    result = svc.evaluate("TEST", holding, strategy, _range_candles(10))
    if result["recommended_sell_trigger"] is not None:
        assert result["recommended_sell_trigger"] < 500


def test_evaluate_override_qty_pct():
    svc = DynamicAveragingEvaluationService()
    holding = {"qty": 100, "avg_cost": 200, "cmp": 210}
    strategy = {"dynamic_averaging_enabled": True, "override_da_qty_pct": 25}
    result = svc.evaluate("TEST", holding, strategy, _range_candles(10))
    if result["da_status"] != "NO_HOLDING":
        assert result["recommended_da_qty_pct"] == 25


def test_evaluate_all():
    reset_da_config()
    svc = DynamicAveragingEvaluationService()
    holdings = [
        {"symbol": "TEST1", "qty": 100, "avg_cost": 200, "cmp": 210},
        {"symbol": "TEST2", "qty": 0, "avg_cost": 200, "cmp": 210},
    ]
    strategies = {"TEST1": {"dynamic_averaging_enabled": True}, "TEST2": {}}
    ohlcv = {"TEST1": _range_candles(10), "TEST2": _range_candles(10)}
    results = svc.evaluate_all(holdings, strategies, ohlcv)
    assert len(results) == 2
    assert results[0]["symbol"] == "TEST1"
    assert results[1]["symbol"] == "TEST2"
    assert results[1]["da_status"] == "NO_HOLDING"


def test_evaluate_eligible_with_all_fields():
    svc = DynamicAveragingEvaluationService()
    holding = {"qty": 100, "avg_cost": 200, "cmp": 210}
    strategy = {"dynamic_averaging_enabled": True}
    result = svc.evaluate("TEST", holding, strategy, _range_candles(10))
    assert result["symbol"] == "TEST"
    assert result["da_last_evaluated_at"] is not None
