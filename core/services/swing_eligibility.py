"""Swing eligibility evaluation for entry strategies."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import pandas as pd

from core.strategy_config import get_strategy_config

logger = logging.getLogger("tradecraftx.swing_eligibility")


class SwingEligibilityService:
    """Evaluate whether a stock is suitable for swing trading based on
    volume, volatility, and trading range criteria over OHLCV data."""

    def evaluate(self, symbol: str, candles: List[Dict]) -> Dict:
        """Run swing eligibility checks for a single symbol.

        Args:
            symbol: Trading symbol.
            candles: OHLCV candle list (sorted by date ascending).
                     Must have at least 20 candles.

        Returns:
            Dict with keys:
              - swing_eligible: bool
              - current_close: float | None
              - ema20: float | None
              - ema50: float | None
              - atr14: float | None
              - avg_volume_20: float | None
              - high_60d: float | None
              - low_60d: float | None
              - atr_percent: float | None
              - range_percent: float | None
              - reasons: list[str] — failure reasons if not eligible
        """
        cfg = get_strategy_config()
        result: Dict = {
            "swing_eligible": False,
            "current_close": None,
            "ema20": None,
            "ema50": None,
            "atr14": None,
            "avg_volume_20": None,
            "high_60d": None,
            "low_60d": None,
            "atr_percent": None,
            "range_percent": None,
            "reasons": [],
        }

        if not candles or len(candles) < 20:
            logger.debug(f"Swing eligibility skipped for {symbol}: insufficient OHLCV ({len(candles or [])})")
            result["reasons"].append("Insufficient OHLCV data")
            return result

        df = pd.DataFrame(candles)
        close_series = pd.to_numeric(df["close"], errors="coerce")
        high_series = pd.to_numeric(df["high"], errors="coerce")
        low_series = pd.to_numeric(df["low"], errors="coerce")
        volume_series = pd.to_numeric(df.get("volume", 0), errors="coerce")

        current_close = float(close_series.iloc[-1])
        result["current_close"] = current_close

        # EMA20 / EMA50
        ema20_series = close_series.ewm(span=cfg.ema_fast_period, adjust=False).mean()
        ema50_series = close_series.ewm(span=cfg.ema_slow_period, adjust=False).mean()
        result["ema20"] = float(ema20_series.iloc[-1])
        if len(candles) >= cfg.ema_slow_period:
            result["ema50"] = float(ema50_series.iloc[-1])

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
        result["atr14"] = atr14

        # 20-day average volume
        recent_volumes = volume_series.tail(cfg.volume_average_days)
        avg_volume = float(recent_volumes.mean()) if len(recent_volumes) > 0 else 0.0
        result["avg_volume_20"] = avg_volume

        # 60-day high/low
        high_60d = float(high_series.max())
        low_60d = float(low_series.min())
        result["high_60d"] = high_60d
        result["low_60d"] = low_60d

        atr_percent = (atr14 / current_close * 100) if current_close > 0 else 0.0
        range_percent = ((high_60d - low_60d) / current_close * 100) if current_close > 0 else 0.0
        result["atr_percent"] = round(atr_percent, 2)
        result["range_percent"] = round(range_percent, 2)

        # --- Checks ---
        eligible = True

        if avg_volume < cfg.minimum_avg_volume:
            eligible = False
            result["reasons"].append(
                f"Low volume: {avg_volume:.0f} < {cfg.minimum_avg_volume}"
            )

        if atr_percent < cfg.minimum_atr_percent:
            eligible = False
            result["reasons"].append(
                f"Low ATR%: {atr_percent:.2f}% < {cfg.minimum_atr_percent}%"
            )

        if range_percent < cfg.minimum_trading_range_percent:
            eligible = False
            result["reasons"].append(
                f"Narrow range: {range_percent:.2f}% < {cfg.minimum_trading_range_percent}%"
            )

        result["swing_eligible"] = eligible

        if eligible:
            logger.info(f"Swing eligibility PASS: {symbol} (vol={avg_volume:.0f}, atr%={atr_percent:.2f}, range%={range_percent:.2f})")
        else:
            logger.info(f"Swing eligibility FAIL: {symbol} - {'; '.join(result['reasons'])}")

        return result


_swing_eligibility_service: SwingEligibilityService | None = None


def get_swing_eligibility_service() -> SwingEligibilityService:
    global _swing_eligibility_service
    if _swing_eligibility_service is None:
        _swing_eligibility_service = SwingEligibilityService()
    return _swing_eligibility_service
