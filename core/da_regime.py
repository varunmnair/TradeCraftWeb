"""Regime classification for system-driven Dynamic Averaging.

Classifies the current price decline into one of three regimes:
- REVERSAL_LIKELY: price appears to be stabilizing or bouncing
- NEUTRAL: mixed signals, no clear direction
- STILL_FALLING: price continues to decline with bearish momentum

Uses only OHLCV data and simple indicators (no RSI, MACD, OBV).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RegimeResult:
    regime: str  # "REVERSAL_LIKELY" | "NEUTRAL" | "STILL_FALLING"
    reversal_score: int
    falling_score: int
    atr: float
    atr_pct: float
    avg_volume: float
    support_price: float | None = None
    support_held: bool = False
    support_broken: bool = False
    recent_candles: list[dict] = field(default_factory=list)


def _build_ema(values: list[float], period: int) -> list[float | None]:
    if len(values) < period:
        return [None] * len(values)
    result: list[float | None] = [None] * (period - 1)
    sma = sum(values[:period]) / period
    result.append(sma)
    multiplier = 2 / (period + 1)
    for i in range(period, len(values)):
        ema = (values[i] - result[-1]) * multiplier + result[-1]
        result.append(ema)
    return result


def _atr(candles: list[dict], period: int = 14) -> float:
    if len(candles) < 2:
        return 0.0
    tr_sum = 0.0
    for i in range(1, min(len(candles), period + 1)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i - 1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_sum += tr
    count = min(len(candles) - 1, period)
    return tr_sum / count if count > 0 else 0.0


def classify_regime(
    candles: list[dict],
    ema_fast_period: int = 20,
    ema_slow_period: int = 50,
    volume_avg_days: int = 20,
    lookback_days: int = 20,
) -> RegimeResult:
    """Classify the current price regime based on recent OHLCV data.

    Args:
        candles: List of OHLCV dicts sorted by date ascending.
        ema_fast_period: Fast EMA period (default 20).
        ema_slow_period: Slow EMA period (default 50).
        volume_avg_days: Period for average volume calculation.
        lookback_days: Number of recent candles to analyze.

    Returns:
        RegimeResult with regime classification, scores, ATR, and support details.
    """
    default_result = RegimeResult(
        regime="NEUTRAL",
        reversal_score=0,
        falling_score=0,
        atr=0.0,
        atr_pct=0.0,
        avg_volume=0.0,
    )

    if not candles or len(candles) < 5:
        return default_result

    recent = candles[-lookback_days:] if len(candles) >= lookback_days else candles
    closes = [c["close"] for c in recent]
    lows = [c["low"] for c in recent]
    volumes = [c["volume"] for c in recent if c.get("volume")]
    atr = _atr(recent)
    cmp_price = closes[-1] if closes else 0
    atr_pct = (atr / cmp_price * 100) if cmp_price > 0 else 0

    avg_volume = (
        sum(volumes[-volume_avg_days:]) / len(volumes[-volume_avg_days:])
        if volumes and len(volumes) >= volume_avg_days
        else (sum(volumes) / len(volumes) if volumes else 0)
    )

    # --- Support detection ---
    support_low = min(lows) if lows else 0
    support_held = False
    support_broken = False

    if len(recent) >= 3:
        # Find support as recent swing low (min of lows in prior candles)
        prior_lows = lows[:-2]
        if prior_lows:
            support_low = min(prior_lows)
            last_two_lows = lows[-2:]

            # Support held: last 2-3 candles' lows stayed above or at support
            if all(lo >= support_low for lo in last_two_lows):
                support_held = True

            # Support broken: last candle closed below support
            if cmp_price < support_low:
                support_broken = True

    # --- Reversal score ---
    reversal_score = 0

    # 1. Latest close > previous close
    if len(closes) >= 2 and closes[-1] > closes[-2]:
        reversal_score += 1

    # 2. Latest low > previous low
    if len(lows) >= 2 and lows[-1] > lows[-2]:
        reversal_score += 1

    # 3. Latest candle is green
    if recent and recent[-1]["close"] > recent[-1]["open"]:
        reversal_score += 1

    # 4. Close above 3-day average close
    if len(closes) >= 3:
        avg3 = sum(closes[-3:]) / 3
        if closes[-1] > avg3:
            reversal_score += 1

    # 5. No new lows in last 2-3 candles
    if len(lows) >= 4:
        recent_lows = lows[-3:]
        prior_low = min(lows[:-3]) if len(lows) > 3 else lows[0]
        if all(x >= prior_low for x in recent_lows):
            reversal_score += 1

    # 6. Volume >= 20-day average volume
    if avg_volume > 0 and volumes and volumes[-1] >= avg_volume:
        reversal_score += 1

    # 7. CMP near recent support (within 1 ATR)
    if support_low > 0 and atr > 0:
        distance_from_support = abs(cmp_price - support_low)
        if distance_from_support <= atr:
            reversal_score += 1
        # Support held for 2-3 candles
        if support_held:
            reversal_score += 1

    # --- Falling score ---
    falling_score = 0

    # 1. Latest close < previous close
    if len(closes) >= 2 and closes[-1] < closes[-2]:
        falling_score += 1

    # 2. Latest low < previous low
    if len(lows) >= 2 and lows[-1] < lows[-2]:
        falling_score += 1

    # 3. Consecutive lower closes
    consec_closes = 0
    for i in range(len(closes) - 1, 0, -1):
        if closes[i] < closes[i - 1]:
            consec_closes += 1
        else:
            break
    if consec_closes >= 2:
        falling_score += 1

    # 4. Consecutive lower lows
    consec_lows = 0
    for i in range(len(lows) - 1, 0, -1):
        if lows[i] < lows[i - 1]:
            consec_lows += 1
        else:
            break
    if consec_lows >= 2:
        falling_score += 1

    # 5. CMP below EMA20
    all_closes = [c["close"] for c in candles]
    ema20 = _build_ema(all_closes, ema_fast_period)
    ema50 = _build_ema(all_closes, ema_slow_period)
    valid_ema20 = [e for e in ema20 if e is not None]
    valid_ema50 = [e for e in ema50 if e is not None]

    if valid_ema20:
        current_ema20 = valid_ema20[-1]
        if cmp_price < current_ema20:
            falling_score += 1

        # 6. EMA20 sloping down
        if len(valid_ema20) >= 2 and valid_ema20[-1] < valid_ema20[-2]:
            falling_score += 1

        # 7. EMA20 < EMA50
        if valid_ema50 and current_ema20 < valid_ema50[-1]:
            falling_score += 1

    # 8. Volume expanding on red candles
    if recent and avg_volume > 0:
        last = recent[-1]
        if last["close"] < last["open"] and last.get("volume", 0) > avg_volume:
            falling_score += 1

    # 9. Recent support broken
    if support_broken:
        falling_score += 1
        # Last 2 candles remain below support
        if len(closes) >= 2 and all(c < support_low for c in closes[-2:]):
            falling_score += 1

    # --- Classification ---
    if reversal_score >= falling_score + 2:
        regime = "REVERSAL_LIKELY"
    elif falling_score >= reversal_score + 2:
        regime = "STILL_FALLING"
    else:
        regime = "NEUTRAL"

    return RegimeResult(
        regime=regime,
        reversal_score=reversal_score,
        falling_score=falling_score,
        atr=round(atr, 4),
        atr_pct=round(atr_pct, 4),
        avg_volume=round(avg_volume, 2),
        support_price=round(support_low, 2) if support_low > 0 else None,
        support_held=support_held,
        support_broken=support_broken,
        recent_candles=recent[-5:],
    )
