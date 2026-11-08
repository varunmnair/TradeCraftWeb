from __future__ import annotations

from typing import Any


def _swing_highs(candles: list[dict], lookback: int = 3) -> list[float]:
    peaks: list[float] = []
    for i in range(1, len(candles) - 1):
        high = candles[i]["high"]
        left = candles[max(0, i - lookback):i]
        right = candles[i + 1:min(len(candles), i + lookback + 1)]
        if all(high >= c["high"] for c in left) and all(high >= c["high"] for c in right):
            if not peaks or abs(high - peaks[-1]) / (peaks[-1] or 1) > 0.005:
                peaks.append(high)
    return peaks


def _swing_lows(candles: list[dict], lookback: int = 3) -> list[float]:
    troughs: list[float] = []
    for i in range(1, len(candles) - 1):
        low = candles[i]["low"]
        left = candles[max(0, i - lookback):i]
        right = candles[i + 1:min(len(candles), i + lookback + 1)]
        if all(low <= c["low"] for c in left) and all(low <= c["low"] for c in right):
            if not troughs or abs(low - troughs[-1]) / (troughs[-1] or 1) > 0.005:
                troughs.append(low)
    return troughs


def _cluster_values(values: list[float], max_distance_factor: float = 0.015) -> list[list[float]]:
    if not values:
        return []
    sorted_vals = sorted(values)
    clusters: list[list[float]] = [[sorted_vals[0]]]
    for v in sorted_vals[1:]:
        if abs(v - clusters[-1][-1]) / (clusters[-1][-1] or 1) <= max_distance_factor:
            clusters[-1].append(v)
        else:
            clusters.append([v])
    return clusters


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


def compute_range_analysis(candles: list[dict]) -> dict[str, Any]:
    if not candles or len(candles) < 5:
        return {
            "is_range_bound": False,
            "range_high": None,
            "range_low": None,
            "range_width": None,
            "range_pct": None,
            "touch_count": 0,
            "support_touches": 0,
            "resistance_touches": 0,
            "avg_volume": None,
        }

    recent = candles[-10:] if len(candles) >= 10 else candles
    avg_vol = sum(c["volume"] for c in recent if "volume" in c) / len(recent) if recent else 0

    peaks = _swing_highs(recent)
    troughs = _swing_lows(recent)

    if len(peaks) < 1 or len(troughs) < 1:
        range_high = max(c["high"] for c in recent)
        range_low = min(c["low"] for c in recent)
        if range_low <= 0:
            range_low = 1
        width = range_high - range_low
        pct = (width / range_low) * 100
        return {
            "is_range_bound": False,
            "range_high": round(range_high, 2),
            "range_low": round(range_low, 2),
            "range_width": round(width, 2),
            "range_pct": round(pct, 2),
            "touch_count": 0,
            "support_touches": 0,
            "resistance_touches": 0,
            "avg_volume": round(avg_vol, 2),
        }

    avg_tr = _atr(recent)
    max_distance = avg_tr * 1.5 if avg_tr > 0 else 0.015 * (recent[-1]["close"])

    res_clusters = _cluster_values(peaks, max_distance / (recent[-1]["close"] or 1))
    sup_clusters = _cluster_values(troughs, max_distance / (recent[-1]["close"] or 1))

    resistance = res_clusters[-1] if res_clusters else peaks
    support = sup_clusters[0] if sup_clusters else troughs

    resistance_zone_high = max(resistance) if resistance else max(c["high"] for c in recent)
    support_zone_low = min(support) if support else min(c["low"] for c in recent)

    resistance_touches = 0
    for c in recent:
        if abs(c["high"] - resistance_zone_high) / (resistance_zone_high or 1) <= 0.01:
            resistance_touches += 1

    support_touches = 0
    for c in recent:
        if abs(c["low"] - support_zone_low) / (support_zone_low or 1) <= 0.01:
            support_touches += 1

    range_high = round(resistance_zone_high, 2)
    range_low = round(support_zone_low, 2)
    width = round(range_high - range_low, 2)
    pct = round((width / (range_low or 1)) * 100, 2)

    is_range_bound = (
        resistance_touches >= 2
        and support_touches >= 2
        and pct <= 15.0
    )

    return {
        "is_range_bound": is_range_bound,
        "range_high": range_high,
        "range_low": range_low,
        "range_width": width,
        "range_pct": pct,
        "touch_count": resistance_touches + support_touches,
        "support_touches": support_touches,
        "resistance_touches": resistance_touches,
        "avg_volume": round(avg_vol, 2),
    }
