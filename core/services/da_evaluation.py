from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from core.da_config import get_da_config
from core.services.range_analysis import compute_range_analysis


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


def _compute_ema_score(candles: list[dict]) -> int:
    closes = [c["close"] for c in candles]
    ema20 = _build_ema(closes, 20)
    ema50 = _build_ema(closes, 50)

    valid20 = [e for e in ema20 if e is not None]
    valid50 = [e for e in ema50 if e is not None]
    if len(valid20) < 2 or len(valid50) < 2:
        return 50

    current_ema20 = valid20[-1]
    current_ema50 = valid50[-1]
    prev_ema20 = valid20[-2]
    prev_ema50 = valid50[-2]

    if current_ema20 > current_ema50 and prev_ema20 <= prev_ema50:
        return 80
    if current_ema20 > current_ema50:
        if closes[-1] > current_ema20 and closes[-2] > prev_ema20:
            return 90
        return 65
    if current_ema20 < current_ema50 and prev_ema20 >= prev_ema50:
        return 20
    if current_ema20 < current_ema50:
        if closes[-1] < current_ema20 and closes[-2] < prev_ema20:
            return 10
        return 35

    return 50


def _detect_strong_trend(ema_score: int) -> str | None:
    if ema_score >= 85:
        return "strong_bullish"
    if ema_score <= 15:
        return "strong_bearish"
    return None


def _compute_avg_volume(candles: list[dict], period: int = 20) -> float:
    recent = candles[-period:] if len(candles) >= period else candles
    vols = [c["volume"] for c in recent if "volume" in c and c["volume"]]
    if not vols:
        return 0.0
    return sum(vols) / len(vols)


def _estimate_charges(sell_value: float, buyback_value: float) -> float:
    brokerage = min(sell_value * 0.0003, 20) + min(buyback_value * 0.0003, 20)
    stt = sell_value * 0.00025
    exchange_charges = (sell_value + buyback_value) * 0.0000345
    sebi = (sell_value + buyback_value) * 0.000001
    gst = (brokerage + exchange_charges) * 0.18
    stamp = buyback_value * 0.00003
    total = brokerage + stt + exchange_charges + sebi + gst + stamp
    return round(total, 2)


def _compute_da_confidence_score(
    range_pct: float,
    touch_count: int,
    support_touches: int,
    resistance_touches: int,
    avg_vol: float,
    expected_net_profit: float,
    min_profit: float,
    thesis_distance: float,
) -> int:
    range_quality = min(100, max(0, (1 - abs(range_pct - 5) / 15) * 100))
    vol_quality = min(100, avg_vol / 50000 * 100) if avg_vol > 0 else 0
    profit_quality = min(100, (expected_net_profit / max(min_profit, 1)) * 50) if min_profit > 0 else 0
    thesis_quality = min(100, thesis_distance * 20)
    consistency = min(100, (touch_count / 10) * 100)

    score = (
        range_quality * 0.30
        + vol_quality * 0.20
        + profit_quality * 0.25
        + thesis_quality * 0.15
        + consistency * 0.10
    )
    return round(min(100, max(0, score)))


def _confidence_label(score: int, config: dict) -> str:
    if score >= config["confidence_high_threshold"]:
        return "HIGH"
    if score >= config["confidence_medium_threshold"]:
        return "MEDIUM"
    if score >= config["confidence_low_threshold"]:
        return "LOW"
    return "NO_RECOMMENDATION"


def _recommended_qty_pct(score: int, config: dict) -> int:
    if score >= config["confidence_high_threshold"]:
        return config["high_confidence_qty_pct"]
    if score >= config["confidence_medium_threshold"]:
        return config["medium_confidence_qty_pct"]
    if score >= config["confidence_low_threshold"]:
        return config["low_confidence_qty_pct"]
    return 0


def _position_risk_score(
    thesis_distance: float,
    ema_score: int,
    range_pct: float,
    confidence: int,
    holding_age_days: int,
) -> int:
    risk = 50
    risk -= min(20, thesis_distance * 10)
    if ema_score >= 85:
        risk -= 10
    elif ema_score <= 15:
        risk += 10
    if range_pct > 10:
        risk += 10
    elif range_pct < 3:
        risk -= 5
    risk -= min(10, confidence / 10)
    if holding_age_days > 60:
        risk += 10
    elif holding_age_days < 7:
        risk -= 5
    return min(100, max(0, round(risk)))


class DynamicAveragingEvaluationService:
    def evaluate(
        self,
        symbol: str,
        holding: dict[str, Any] | None,
        entry_strategy: dict[str, Any],
        candles: list[dict],
    ) -> dict[str, Any]:
        config = get_da_config()
        now = datetime.now(timezone.utc)
        result: dict[str, Any] = {
            "symbol": symbol,
            "da_eligible": False,
            "da_status": None,
            "da_confidence_score": None,
            "da_confidence_label": None,
            "da_last_evaluated_at": now,
            "da_notes": "",
            "recommended_sell_trigger": None,
            "recommended_sell_limit": None,
            "recommended_buyback_price": None,
            "recommended_da_qty": 0,
            "recommended_da_qty_pct": 0,
            "expected_sell_value": None,
            "expected_buyback_value": None,
            "expected_charges": None,
            "expected_net_profit": None,
            "position_risk_score": None,
            "range_high": None,
            "range_low": None,
            "range_width": None,
            "range_pct": None,
        }

        holding_qty = holding["qty"] if holding else 0
        holding_avg = holding["avg_cost"] if holding else 0
        cmp_price = holding.get("cmp") if holding else None
        if not cmp_price and candles:
            cmp_price = candles[-1]["close"]
        thesis_break_price = entry_strategy.get("thesis_break_price")

        if holding_qty <= 0:
            result["da_status"] = "NO_HOLDING"
            result["da_notes"] = "No holding position"
            return result

        if cmp_price and thesis_break_price and cmp_price <= thesis_break_price:
            result["da_status"] = "THESIS_BREAK"
            result["da_notes"] = "Current price at or below thesis break price"
            return result

        if not candles or len(candles) < 5:
            result["da_status"] = "INSUFFICIENT_DATA"
            result["da_notes"] = "Insufficient OHLCV data for analysis"
            return result

        range_result = compute_range_analysis(candles)
        result["range_high"] = range_result["range_high"]
        result["range_low"] = range_result["range_low"]
        result["range_width"] = range_result["range_width"]
        result["range_pct"] = range_result["range_pct"]

        ema_score = _compute_ema_score(candles)
        strong_trend = _detect_strong_trend(ema_score)
        if strong_trend:
            result["da_status"] = "TRENDING"
            result["da_notes"] = f"Strong {strong_trend} trend detected"
            return result

        avg_volume = _compute_avg_volume(candles)
        result["avg_volume"] = round(avg_volume, 2)
        if avg_volume < config["minimum_volume_threshold"]:
            result["da_status"] = "LOW_VOLUME"
            result["da_notes"] = f"Average volume {avg_volume:.0f} below threshold {config['minimum_volume_threshold']}"
            return result

        if not range_result["is_range_bound"]:
            result["da_status"] = "INSUFFICIENT_RANGE"
            result["da_notes"] = "Stock is not range-bound"
            return result

        sell_offset_override = entry_strategy.get("override_sell_offset")
        sell_offset = sell_offset_override if sell_offset_override is not None else config["default_sell_offset"]
        sell_trigger = round(range_result["range_high"] * (1 - sell_offset), 2)
        sell_limit = round(sell_trigger * 0.997, 2)
        result["recommended_sell_trigger"] = sell_trigger
        result["recommended_sell_limit"] = sell_limit

        buyback_override = entry_strategy.get("override_buyback_price")
        if buyback_override is not None:
            buyback_price = buyback_override
        else:
            support_mid = (
                range_result["range_low"]
                + (range_result["range_high"] - range_result["range_low"]) * 0.3
            )
            buyback_price = round(support_mid, 2)
        result["recommended_buyback_price"] = buyback_price

        qty_pct_override = entry_strategy.get("override_da_qty_pct")
        if qty_pct_override is not None:
            qty_pct = qty_pct_override
        else:
            qty_pct = config["medium_confidence_qty_pct"]

        sell_qty = int(holding_qty * qty_pct / 100)
        result["recommended_da_qty_pct"] = qty_pct
        result["recommended_da_qty"] = sell_qty

        expected_sell_value = round(sell_qty * sell_trigger, 2)
        expected_buyback_value = round(sell_qty * buyback_price, 2)
        result["expected_sell_value"] = expected_sell_value
        result["expected_buyback_value"] = expected_buyback_value

        charges = _estimate_charges(expected_sell_value, expected_buyback_value)
        result["expected_charges"] = charges

        gross_profit = expected_sell_value - expected_buyback_value
        net_profit = round(gross_profit - charges, 2)
        result["expected_net_profit"] = net_profit

        if net_profit < config["minimum_da_net_profit"]:
            result["da_status"] = "INSUFFICIENT_PROFIT"
            result["da_notes"] = f"Expected net profit ₹{net_profit} below minimum ₹{config['minimum_da_net_profit']}"
            return result

        thesis_distance = 0.0
        if cmp_price and thesis_break_price and thesis_break_price > 0:
            thesis_distance = (cmp_price - thesis_break_price) / thesis_break_price

        score = _compute_da_confidence_score(
            range_pct=range_result["range_pct"] or 0,
            touch_count=range_result["touch_count"],
            support_touches=range_result["support_touches"],
            resistance_touches=range_result["resistance_touches"],
            avg_vol=avg_volume,
            expected_net_profit=net_profit,
            min_profit=config["minimum_da_net_profit"],
            thesis_distance=thesis_distance,
        )
        result["da_confidence_score"] = score
        result["da_confidence_label"] = _confidence_label(score, config)
        result["da_eligible"] = score >= config["no_recommendation_min_score"]

        if result["da_eligible"]:
            result["da_status"] = "ELIGIBLE"

        qty_pct_from_confidence = _recommended_qty_pct(score, config)
        if qty_pct_override is None:
            result["recommended_da_qty_pct"] = qty_pct_from_confidence
            result["recommended_da_qty"] = int(holding_qty * qty_pct_from_confidence / 100)

        holding_age_days = 30
        result["position_risk_score"] = _position_risk_score(
            thesis_distance=thesis_distance,
            ema_score=ema_score,
            range_pct=range_result["range_pct"] or 0,
            confidence=score,
            holding_age_days=holding_age_days,
        )

        notes_parts = []
        if result["da_status"] == "ELIGIBLE":
            notes_parts.append(f"Range: {range_result['range_high']}-{range_result['range_low']}")
            notes_parts.append(f"Confidence: {result['da_confidence_label']} ({score})")
            notes_parts.append(f"Net profit: ₹{net_profit}")
            notes_parts.append(f"Resistance touches: {range_result['resistance_touches']}")
            notes_parts.append(f"Support touches: {range_result['support_touches']}")
        result["da_notes"] = "; ".join(notes_parts)

        return result

    def evaluate_all(
        self,
        holdings: list[dict[str, Any]],
        entry_strategies: dict[str, dict[str, Any]],
        ohlcv_data: dict[str, list[dict]],
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for holding in holdings:
            symbol = holding.get("symbol", "").upper()
            strategy = entry_strategies.get(symbol, {})
            candles = ohlcv_data.get(symbol.replace("-BE", "").replace("#", "").upper(), [])
            result = self.evaluate(symbol, holding, strategy, candles)
            results.append(result)
        return results


_service: DynamicAveragingEvaluationService | None = None


def get_da_evaluation_service() -> DynamicAveragingEvaluationService:
    global _service
    if _service is None:
        _service = DynamicAveragingEvaluationService()
    return _service
