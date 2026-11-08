"""Exit score and exit action computation for holdings."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import pandas as pd

from core.wroi_trend import compute_wroi_trends

logger = logging.getLogger("tradecraftx.exit_scorer")


def _build_ema_df(candles: List[Dict]) -> Optional[pd.DataFrame]:
    """Convert OHLCV candle list to DataFrame with ema20/ema50 columns.

    Returns None if fewer than 20 candles.
    """
    if len(candles) < 20:
        return None

    df = pd.DataFrame(candles)
    close_series = pd.to_numeric(df["close"], errors="coerce")

    df["ema20"] = close_series.ewm(span=20, adjust=False).mean()
    if len(candles) >= 50:
        df["ema50"] = close_series.ewm(span=50, adjust=False).mean()

    return df


def _avg_volume(candles: List[Dict], days: int = 20) -> float:
    """Mean volume over the last N candles."""
    volumes = [c["volume"] for c in candles[-days:] if c.get("volume") is not None]
    return sum(volumes) / len(volumes) if volumes else 0.0


def _ema_structure_score(
    current_close: float, ema20: Optional[float], ema50: Optional[float]
) -> int:
    """Score the EMA structure (max 50 points)."""
    if ema20 is None:
        return 0

    if current_close > ema20:
        if ema50 is not None and ema20 > ema50:
            return 50
        return 35

    if current_close < ema20:
        if ema50 is not None and ema20 < ema50:
            return 0
        return 15

    return 15


def _volume_score(current_volume: float, avg_volume_20: float) -> int:
    """Score volume confirmation (max 30 points)."""
    if avg_volume_20 <= 0:
        return 0

    ratio = current_volume / avg_volume_20
    if ratio > 1.2:
        return 30
    if ratio >= 0.8:
        return 20
    return 0


def _wroi_score(trend: str) -> int:
    """Score WROI trend (max 20 points)."""
    return {
        "STRONG_UP": 20,
        "UP": 15,
        "NEUTRAL": 10,
        "DOWN": 5,
        "STRONG_DOWN": 0,
    }.get(trend, 0)


def _exit_action(score: Optional[int]) -> Optional[str]:
    """Map numeric score to exit action."""
    if score is None:
        return None
    if score >= 80:
        return "HOLD"
    if score >= 60:
        return "WATCH"
    if score >= 40:
        return "REDUCE"
    return "EXIT"


def compute_exit_scores(
    holdings_results: List[Dict],
    ohlcv_by_symbol: Dict[str, List[Dict]],
    total_invested: float,
    wroi_trends: Optional[Dict[str, str]] = None,
) -> List[Dict]:
    """Add exit_score, exit_action, and sub-scores to each holding dict.

    Evaluates EMA structure (50 pts), volume confirmation (30 pts),
    and WROI trend (20 pts) for each holding. Handles missing or
    insufficient OHLCV data gracefully.

    Args:
        holdings_results: List of analyzed holding dicts to modify in-place.
        ohlcv_by_symbol: Dict mapping symbol to OHLCV candle list.
        total_invested: Portfolio total invested for WROI calculation.
        wroi_trends: Optional pre-computed WROI trends dict (skips internal computation).

    Returns:
        The same list (modified in-place) for convenience.
    """
    if not holdings_results:
        logger.debug("No holdings results to score")
        return holdings_results

    logger.info(
        f"Computing exit scores for {len(holdings_results)} holdings "
        f"({len(ohlcv_by_symbol)} symbols with OHLCV)"
    )

    # Build symbol → holding lookup and collect valid symbols for WROI
    holding_by_symbol: Dict[str, Dict] = {}
    for h in holdings_results:
        sym = h.get("symbol", "").replace("-BE", "").replace("#", "").upper()
        holding_by_symbol[sym] = h

    # Compute WROI trends once for all symbols (unless pre-computed)
    if wroi_trends is None:
        wroi_trends = compute_wroi_trends(holdings_results, ohlcv_by_symbol, total_invested)
    logger.debug(f"WROI trends available for {len(wroi_trends)} symbols")

    scored = 0
    skipped = 0

    for h in holdings_results:
        symbol = h.get("symbol", "")
        symbol_clean = symbol.replace("-BE", "").replace("#", "").upper()

        candles = ohlcv_by_symbol.get(symbol_clean)
        if not candles or len(candles) == 0:
            h["exit_score"] = None
            h["exit_action"] = None
            skipped += 1
            logger.debug(f"No OHLCV data for {symbol}, skipping")
            continue

        # --- EMA structure score (50 pts) ---
        df = _build_ema_df(candles)
        if df is not None:
            current_close = float(candles[-1]["close"])
            ema20 = float(df["ema20"].iloc[-1]) if df["ema20"].notna().iloc[-1] else None
            ema50 = (
                float(df["ema50"].iloc[-1])
                if "ema50" in df.columns and df["ema50"].notna().iloc[-1]
                else None
            )
            ema_score = _ema_structure_score(current_close, ema20, ema50)
        else:
            ema_score = 0

        # --- Volume confirmation score (30 pts) ---
        current_volume = candles[-1].get("volume")
        if current_volume is not None and current_volume > 0:
            avg_vol = _avg_volume(candles)
            volume_score = _volume_score(float(current_volume), avg_vol)
        else:
            volume_score = 0

        # --- WROI trend score (20 pts) ---
        trend = wroi_trends.get(symbol_clean, "NA")
        wroi_score_val = _wroi_score(trend)

        total_score = ema_score + volume_score + wroi_score_val
        h["exit_score"] = total_score
        h["exit_action"] = _exit_action(total_score)
        h["ema_score"] = ema_score
        h["volume_score"] = volume_score
        h["wroi_score"] = wroi_score_val

        # BREAK overrides all other signals
        if h.get("thesis_broken"):
            h["exit_score"] = 0
            h["exit_action"] = "BREAK"

        scored += 1
        logger.debug(
            f"{symbol}: ema={ema_score}/50 vol={volume_score}/30 wroi={wroi_score_val}/20 "
            f"total={total_score}/100 action={h['exit_action']}"
        )

    logger.info(f"Exit scores computed: {scored} scored, {skipped} skipped")
    return holdings_results
