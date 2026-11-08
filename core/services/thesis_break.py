"""Thesis break calculation and detection for entry strategies."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import pandas as pd

from core.strategy_config import get_strategy_config

logger = logging.getLogger("tradecraftx.thesis_break")


class ThesisBreakService:
    """Calculate thesis break levels and detect breaches to protect capital."""

    def calculate(
        self,
        symbol: str,
        entry3_price: float,
        candles: List[Dict],
    ) -> Optional[float]:
        """Calculate thesis break price below entry3.

        Uses the nearest support region below entry3 minus ATR14.

        Args:
            symbol: Trading symbol.
            entry3_price: Third entry level (lowest).
            candles: OHLCV candle list.

        Returns:
            Thesis break price, or None if insufficient data.
        """
        cfg = get_strategy_config()

        if not candles or len(candles) < cfg.atr_period:
            logger.debug(f"Thesis break skipped for {symbol}: insufficient OHLCV")
            return None

        df = pd.DataFrame(candles)
        high_series = pd.to_numeric(df["high"], errors="coerce")
        low_series = pd.to_numeric(df["low"], errors="coerce")
        close_series = pd.to_numeric(df["close"], errors="coerce")

        # ATR14
        prev_close = close_series.shift(1)
        tr = pd.concat(
            [
                (high_series - low_series).abs(),
                (high_series - prev_close).abs(),
                (low_series - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr14 = float(tr.rolling(window=cfg.atr_period).mean().iloc[-1])

        # Find nearest support below entry3
        support = self._nearest_support_below(entry3_price, low_series, atr14)

        thesis_break = round(support - atr14, 2)

        logger.info(f"Thesis break calculated for {symbol}: entry3={entry3_price} support={support} atr={atr14} thesis_break={thesis_break}")

        return thesis_break

    def detect_breach(
        self, symbol: str, current_close: float, thesis_break_price: float, review_status: Optional[str] = None
    ) -> bool:
        """Check if current close has breached thesis break level."""
        if thesis_break_price is None:
            return False

        breached = current_close <= thesis_break_price
        if breached:
            logger.warning(
                f"Thesis break DETECTED for {symbol}: "
                f"close={current_close} <= thesis_break={thesis_break_price} "
                f"(previous status: {review_status or 'ACTIVE'})"
            )
        return breached

    def evaluate(
        self,
        symbol: str,
        levels: list[dict],
        candles: list[dict],
    ) -> dict:
        """Evaluate whether the thesis is broken for a symbol.

        Args:
            symbol: Trading symbol.
            levels: List of entry level dicts with 'level_no' and 'price'.
            candles: OHLCV candle list.

        Returns:
            Dict with 'thesis_broken' (bool) and 'reason' (str | None).
        """
        entry3_price = None
        for level in levels:
            if level.get("level_no") == 3:
                entry3_price = level.get("price")
                break
        if entry3_price is None and levels:
            entry3_price = levels[-1].get("price")

        thesis_break_price = self.calculate(symbol, entry3_price, candles) if entry3_price else None

        if thesis_break_price and candles:
            current_close = candles[-1]["close"]
            breached = self.detect_breach(symbol, current_close, thesis_break_price)
            if breached:
                return {"thesis_broken": True, "reason": f"Thesis break at ₹{thesis_break_price}"}

        return {"thesis_broken": False, "reason": None}

    def _nearest_support_below(
        self, price: float, low_series: pd.Series, atr: float
    ) -> float:
        """Find the nearest support level below a given price using swing low clustering."""
        cfg = get_strategy_config()
        lookback = cfg.range_analysis_days
        lows = low_series.tail(lookback).values

        # Cluster lows within 1.5x ATR
        sorted_lows = sorted(lows)
        clusters: list[list[float]] = [[sorted_lows[0]]]

        for v in sorted_lows[1:]:
            if abs(v - clusters[-1][-1]) <= atr * 1.5:
                clusters[-1].append(v)
            else:
                clusters.append([v])

        # Filter clusters with 2+ touches, below the price
        significant_supports = [
            sum(c) / len(c)
            for c in clusters
            if len(c) >= 2 and (sum(c) / len(c)) < price
        ]

        if significant_supports:
            return max(significant_supports)

        # Fallback: use the highest low below entry3, but ensure at least 1 ATR gap
        lows_below = [low for low in sorted_lows if low < price]
        if lows_below:
            fallback = max(lows_below)
            if fallback > price - atr:
                fallback = price - atr
            return fallback
        return price - atr


_thesis_break_service: ThesisBreakService | None = None


def get_thesis_break_service() -> ThesisBreakService:
    global _thesis_break_service
    if _thesis_break_service is None:
        _thesis_break_service = ThesisBreakService()
    return _thesis_break_service
