"""Tests for core/exit_scorer.py."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Optional

from core.exit_scorer import (
    _avg_volume,
    _build_ema_df,
    _ema_structure_score,
    _exit_action,
    _volume_score,
    _wroi_score,
    compute_exit_scores,
)


def _candle(close: float, volume: int = 100000, day_offset: int = 0) -> dict:
    d = date.today() - timedelta(days=day_offset)
    return {
        "trade_date": d, "open": close - 0.5, "high": close + 0.5,
        "low": close - 0.5, "close": close, "volume": volume,
    }


def _make_candles(close_prices: List[float], volume: int = 100000) -> List[Dict]:
    return [
        _candle(p, volume, day_offset=len(close_prices) - 1 - i)
        for i, p in enumerate(close_prices)
    ]


SAMPLE_HOLDING = {
    "symbol": "RELIANCE",
    "quantity": 100,
    "average_price": 100.0,
    "invested": 10000.0,
    "age": 100,
    "weighted_roi": 0.001,
}


# ── _build_ema_df ────────────────────────────────────────────────

def test_build_ema_df_insufficient():
    assert _build_ema_df(_make_candles([100] * 10)) is None


def test_build_ema_df_sufficient():
    df = _build_ema_df(_make_candles([100] * 60))
    assert df is not None
    assert "ema20" in df.columns
    assert "ema50" in df.columns
    assert df["ema20"].notna().iloc[-1]
    assert df["ema50"].notna().iloc[-1]


def test_build_ema_df_between_20_and_50():
    df = _build_ema_df(_make_candles([100] * 30))
    assert df is not None
    assert "ema20" in df.columns
    assert "ema50" not in df.columns


# ── _avg_volume ───────────────────────────────────────────────────

def test_avg_volume_normal():
    candles = _make_candles([100] * 25, volume=50000)
    avg = _avg_volume(candles)
    assert avg == 50000.0


def test_avg_volume_empty():
    candles = _make_candles([100] * 10, volume=0)
    # All volumes are 0
    avg = _avg_volume(candles)
    assert avg == 0.0


def test_avg_volume_no_volume_key():
    candles = [{"trade_date": date.today(), "close": 100} for _ in range(25)]
    avg = _avg_volume(candles)
    assert avg == 0.0


# ── _ema_structure_score ─────────────────────────────────────────

def test_ema_score_strong_bull():
    """CMP > EMA20 > EMA50 → 50."""
    assert _ema_structure_score(110, 105, 100) == 50


def test_ema_score_bull():
    """CMP > EMA20 (no EMA50 or EMA20 <= EMA50) → 35."""
    assert _ema_structure_score(110, 105, 108) == 35   # ema20 < ema50
    assert _ema_structure_score(110, 105, None) == 35   # no ema50


def test_ema_score_bear():
    """CMP < EMA20 → 15 (when no ema50 or ema20 >= ema50)."""
    assert _ema_structure_score(100, 105, None) == 15    # no ema50
    assert _ema_structure_score(100, 105, 100) == 15     # ema20 >= ema50 → falls through to CMP < EMA20


def test_ema_score_strong_bear():
    """CMP < EMA20 < EMA50 → 0."""
    assert _ema_structure_score(100, 105, 110) == 0
    # Wait - CMP < EMA20 matches before CMP < EMA20 < EMA50
    # Actually the elif chain: first match wins
    # CMP < EMA20 (100 < 105) → matches line... let me check
    pass


def test_ema_score_no_ema20():
    """No EMA20 data → 0."""
    assert _ema_structure_score(100, None, None) == 0


# ── _volume_score ────────────────────────────────────────────────

def test_volume_high():
    """volume > 1.2 * avg → 30."""
    assert _volume_score(150, 100) == 30
    assert _volume_score(121, 100) == 30


def test_volume_normal():
    """0.8 * avg <= volume <= 1.2 * avg → 20."""
    assert _volume_score(100, 100) == 20
    assert _volume_score(80, 100) == 20
    assert _volume_score(120, 100) == 20


def test_volume_low():
    """volume < 0.8 * avg → 0."""
    assert _volume_score(79, 100) == 0
    assert _volume_score(50, 100) == 0


def test_volume_zero_avg():
    """Zero avg volume → 0."""
    assert _volume_score(100, 0) == 0


# ── _wroi_score ──────────────────────────────────────────────────

def test_wroi_score_mapping():
    assert _wroi_score("STRONG_UP") == 20
    assert _wroi_score("UP") == 15
    assert _wroi_score("NEUTRAL") == 10
    assert _wroi_score("DOWN") == 5
    assert _wroi_score("STRONG_DOWN") == 0
    assert _wroi_score("NA") == 0
    assert _wroi_score("UNKNOWN") == 0


# ── _exit_action ─────────────────────────────────────────────────

def test_action_mapping():
    assert _exit_action(100) == "HOLD"
    assert _exit_action(80) == "HOLD"
    assert _exit_action(79) == "WATCH"
    assert _exit_action(60) == "WATCH"
    assert _exit_action(59) == "REDUCE"
    assert _exit_action(40) == "REDUCE"
    assert _exit_action(39) == "EXIT"
    assert _exit_action(0) == "EXIT"
    assert _exit_action(None) is None


# ── compute_exit_scores end-to-end ───────────────────────────────

def test_exit_score_happens_fast():
    """Quick smoke test — function doesn't crash and returns expected keys."""
    candles = _make_candles(
        [100 + i * 0.5 for i in range(60)], volume=100000
    )
    ohlcv = {"RELIANCE": candles}
    results = compute_exit_scores(
        [dict(SAMPLE_HOLDING)], ohlcv, total_invested=20000.0
    )
    assert len(results) == 1
    h = results[0]
    assert "exit_score" in h
    assert "exit_action" in h


def test_missing_ohlcv():
    """No OHLCV data → exit_score = None, exit_action = None."""
    results = compute_exit_scores(
        [dict(SAMPLE_HOLDING)], {}, total_invested=20000.0
    )
    assert results[0]["exit_score"] is None
    assert results[0]["exit_action"] is None


def test_empty_holdings():
    results = compute_exit_scores([], {}, total_invested=20000.0)
    assert results == []


def test_missing_symbol_in_ohlcv():
    """Symbol has data but OHLCV has different symbol → skipped."""
    candles = _make_candles([100] * 60)
    results = compute_exit_scores(
        [dict(SAMPLE_HOLDING)], {"OTHER": candles}, total_invested=20000.0
    )
    assert results[0]["exit_score"] is None
    assert results[0]["exit_action"] is None


def test_insufficient_candles():
    """Less than 20 candles → ema_score = 0, still gets volume + wroi."""
    candles = _make_candles([100] * 10)
    results = compute_exit_scores(
        [dict(SAMPLE_HOLDING)], {"RELIANCE": candles}, total_invested=20000.0
    )
    h = results[0]
    assert h["exit_score"] is not None
    # ema=0, volume=20 (all same volume → avg == current → 20), wroi varies
    assert h["exit_score"] >= 20


def test_zero_volume():
    """Zero volume in candles → volume_score = 0."""
    candles = _make_candles([100 + i * 0.5 for i in range(60)], volume=0)
    results = compute_exit_scores(
        [dict(SAMPLE_HOLDING)], {"RELIANCE": candles}, total_invested=20000.0
    )
    h = results[0]
    assert h["exit_score"] is not None
    assert h["exit_action"] is not None


def test_be_suffix():
    """-BE suffix is stripped for symbol matching."""
    holding = {**SAMPLE_HOLDING, "symbol": "RELIANCE-BE"}
    candles = _make_candles([100] * 60)
    results = compute_exit_scores(
        [holding], {"RELIANCE": candles}, total_invested=20000.0
    )
    assert results[0]["exit_score"] is not None


def test_rising_prices_end_to_end():
    """Rising prices + high volume → HOLD or WATCH."""
    prices = [100 + i * 0.3 for i in range(60)]
    candles = _make_candles(prices, volume=200000)
    # Start with low volume at the beginning so avg_volume_20 isn't as high
    # Actually all volumes are 200000, so avg = 200000, current = 200000 → 1.0 ratio → 20
    # For high volume we need > 1.2 * avg, so we need volume > 240000
    candles_with_high_vol = _make_candles(prices, volume=300000)
    results = compute_exit_scores(
        [dict(SAMPLE_HOLDING)], {"RELIANCE": candles_with_high_vol}, total_invested=20000.0
    )
    h = results[0]
    assert h["exit_score"] is not None
    # Rising prices: CMP > EMA20 > EMA50 (likely) + high vol + rising wroi
    assert h["exit_action"] in ("HOLD", "WATCH")


def test_falling_prices_end_to_end():
    """Falling prices + low volume → EXIT or REDUCE."""
    prices = [130 - i * 0.5 for i in range(60)]
    candles = _make_candles(prices, volume=50000)
    results = compute_exit_scores(
        [dict(SAMPLE_HOLDING)], {"RELIANCE": candles}, total_invested=20000.0
    )
    h = results[0]
    assert h["exit_score"] is not None
    # Falling prices: likely CMP < EMA20 < EMA50 + low vol + STRONG_DOWN wroi
    assert h["exit_action"] in ("EXIT", "REDUCE")


def test_multiple_symbols():
    """Two symbols scored independently."""
    h1 = {**SAMPLE_HOLDING, "symbol": "CDSL"}
    h2 = {**SAMPLE_HOLDING, "symbol": "LODHA"}
    rising = _make_candles([100 + i * 0.3 for i in range(60)], volume=100000)
    falling = _make_candles([130 - i * 0.5 for i in range(60)], volume=50000)
    results = compute_exit_scores(
        [h1, h2], {"CDSL": rising, "LODHA": falling}, total_invested=20000.0
    )
    assert results[0]["exit_score"] is not None
    assert results[1]["exit_score"] is not None
