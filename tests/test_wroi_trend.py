"""Tests for core/wroi_trend.py."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List

from core.wroi_trend import compute_wroi_trends


def _make_candle(close: float, day_offset: int = 0) -> dict:
    d = date.today() - timedelta(days=day_offset)
    return {"trade_date": d, "open": close, "high": close, "low": close, "close": close, "volume": 1000}


def _candles_from_prices(prices: List[float]) -> List[Dict]:
    return [_make_candle(p, day_offset=len(prices) - 1 - i) for i, p in enumerate(prices)]


SAMPLE_HOLDING = {
    "symbol": "RELIANCE",
    "quantity": 100,
    "average_price": 100.0,
    "invested": 10000.0,
    "age": 100,
    "weighted_roi": 0.001,
}


def test_strong_up():
    prices = [95.0, 97.0, 99.0, 101.0, 103.0, 105.0]
    ohlcv = {"RELIANCE": _candles_from_prices(prices)}
    trends = compute_wroi_trends([SAMPLE_HOLDING], ohlcv, total_invested=20000.0)
    assert trends.get("RELIANCE") == "STRONG_UP"


def test_strong_down():
    prices = [105.0, 103.0, 101.0, 99.0, 97.0, 95.0]
    ohlcv = {"RELIANCE": _candles_from_prices(prices)}
    trends = compute_wroi_trends([SAMPLE_HOLDING], ohlcv, total_invested=20000.0)
    assert trends.get("RELIANCE") == "STRONG_DOWN"


def test_up():
    """4 up, 1 down → UP."""
    prices = [95.0, 97.0, 99.0, 101.0, 103.0, 100.0]
    ohlcv = {"RELIANCE": _candles_from_prices(prices)}
    trends = compute_wroi_trends([SAMPLE_HOLDING], ohlcv, total_invested=20000.0)
    assert trends.get("RELIANCE") == "UP"


def test_down():
    """4 down, 1 up → DOWN."""
    prices = [105.0, 103.0, 101.0, 99.0, 97.0, 100.0]
    ohlcv = {"RELIANCE": _candles_from_prices(prices)}
    trends = compute_wroi_trends([SAMPLE_HOLDING], ohlcv, total_invested=20000.0)
    assert trends.get("RELIANCE") == "DOWN"


def test_neutral_mixed():
    """Mixed moves → NEUTRAL."""
    prices = [95.0, 100.0, 105.0, 100.0, 95.0, 100.0]
    ohlcv = {"RELIANCE": _candles_from_prices(prices)}
    trends = compute_wroi_trends([SAMPLE_HOLDING], ohlcv, total_invested=20000.0)
    assert trends.get("RELIANCE") == "NEUTRAL"


def test_neutral_flat():
    """All flat prices → NEUTRAL."""
    prices = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0]
    ohlcv = {"RELIANCE": _candles_from_prices(prices)}
    trends = compute_wroi_trends([SAMPLE_HOLDING], ohlcv, total_invested=20000.0)
    assert trends.get("RELIANCE") == "NEUTRAL"


def test_insufficient_candles():
    """Only 3 candles → NA."""
    ohlcv = {"RELIANCE": _candles_from_prices([95.0, 97.0, 99.0])}
    trends = compute_wroi_trends([SAMPLE_HOLDING], ohlcv, total_invested=20000.0)
    assert trends.get("RELIANCE") == "NA"


def test_no_age():
    """No age data → NA."""
    holding = {**SAMPLE_HOLDING, "age": None}
    ohlcv = {"RELIANCE": _candles_from_prices([95.0, 97.0, 99.0, 101.0, 103.0, 105.0])}
    trends = compute_wroi_trends([holding], ohlcv, total_invested=20000.0)
    assert trends.get("RELIANCE") == "NA"


def test_zero_invested():
    """Zero invested → NA."""
    holding = {**SAMPLE_HOLDING, "quantity": 0, "invested": 0}
    ohlcv = {"RELIANCE": _candles_from_prices([95.0, 97.0, 99.0, 101.0, 103.0, 105.0])}
    trends = compute_wroi_trends([holding], ohlcv, total_invested=20000.0)
    assert trends.get("RELIANCE") == "NA"


def test_empty_holdings():
    trends = compute_wroi_trends([], {}, total_invested=20000.0)
    assert trends == {}


def test_missing_symbol_in_ohlcv():
    """Symbol in OHLCV but not in holdings → NA."""
    ohlcv = {"UNKNOWN": _candles_from_prices([95.0, 97.0, 99.0, 101.0, 103.0, 105.0])}
    trends = compute_wroi_trends([SAMPLE_HOLDING], ohlcv, total_invested=20000.0)
    assert trends.get("UNKNOWN") == "NA"
    assert "RELIANCE" not in trends


def test_symbol_with_be_suffix():
    """Symbols ending with -BE get cleaned."""
    holding = {**SAMPLE_HOLDING, "symbol": "RELIANCE-BE"}
    prices = [95.0, 97.0, 99.0, 101.0, 103.0, 105.0]
    ohlcv = {"RELIANCE": _candles_from_prices(prices)}
    trends = compute_wroi_trends([holding], ohlcv, total_invested=20000.0)
    assert trends.get("RELIANCE") == "STRONG_UP"


def test_multiple_symbols():
    """Two symbols with opposite trends."""
    h1 = {**SAMPLE_HOLDING, "symbol": "CDSL"}
    h2 = {"symbol": "TCS", "quantity": 200, "average_price": 100.0, "invested": 20000.0, "age": 100, "weighted_roi": 0.001}
    ohlcv = {
        "CDSL": _candles_from_prices([95.0, 97.0, 99.0, 101.0, 103.0, 105.0]),
        "TCS": _candles_from_prices([105.0, 103.0, 101.0, 99.0, 97.0, 95.0]),
    }
    trends = compute_wroi_trends([h1, h2], ohlcv, total_invested=30000.0)
    assert trends.get("CDSL") == "STRONG_UP"
    assert trends.get("TCS") == "STRONG_DOWN"


def test_age_zero():
    """Age=0 → all historical_age = 1."""
    holding = {**SAMPLE_HOLDING, "age": 0}
    prices = [95.0, 97.0, 99.0, 101.0, 103.0, 105.0]
    ohlcv = {"RELIANCE": _candles_from_prices(prices)}
    trends = compute_wroi_trends([holding], ohlcv, total_invested=20000.0)
    assert trends.get("RELIANCE") == "STRONG_UP"
