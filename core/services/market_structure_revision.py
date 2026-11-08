"""Market structure based entry level revision suggestions."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd

from core.strategy_config import get_strategy_config

logger = logging.getLogger("tradecraftx.market_structure_revision")

_STYLE_MULTIPLIERS = {
    "balanced": (1.0, 0.03),
    "conservative": (1.5, 0.04),
    "aggressive": (0.75, 0.02),
}


class MarketStructureRevisionService:
    """Suggest revised entry levels based on current market structure,
    support/resistance zones, and ATR spacing."""

    def suggest_revision(
        self,
        symbol: str,
        current_levels: List[Dict[str, Any]],
        candles: List[Dict],
        cmp_price: float | None = None,
        style: str = "balanced",
    ) -> Dict[str, Any]:
        """Generate revision suggestion using market structure analysis.

        Args:
            symbol: Trading symbol.
            current_levels: List of dicts with level_no, price.
            candles: OHLCV candle list (sorted ascending).
            cmp_price: Optional current market price (fetched if not provided).
            style: Revision style — "balanced", "conservative", or "aggressive".

        Returns:
            Dict with keys:
              - suggested_entry1, suggested_entry2, suggested_entry3: float
              - revision_reason: str
              - thesis_break_price: float
              - style: str
        """
        cfg = get_strategy_config()

        from core.market_data.ohlcv_store import ensure_ohlcv, get_ohlcv_multi

        symbol_clean = symbol.replace("-BE", "").replace("#", "").upper()
        ensure_ohlcv([symbol_clean], days=cfg.range_analysis_days)
        ohlcv_data = get_ohlcv_multi([symbol_clean], days=cfg.range_analysis_days)
        db_candles = ohlcv_data.get(symbol_clean, [])
        if db_candles:
            candles = db_candles

        result: Dict[str, Any] = {
            "suggested_entry1": None,
            "suggested_entry2": None,
            "suggested_entry3": None,
            "revision_reason": None,
            "thesis_break_price": None,
            "style": style,
            "atr14": None,
            "current_close": None,
        }

        if not candles or len(candles) < 20:
            logger.debug(f"Market structure revision skipped for {symbol}: insufficient OHLCV")
            result["revision_reason"] = "Insufficient OHLCV data"
            return result

        df = pd.DataFrame(candles)
        close_series = pd.to_numeric(df["close"], errors="coerce")
        high_series = pd.to_numeric(df["high"], errors="coerce")
        low_series = pd.to_numeric(df["low"], errors="coerce")

        current_close = float(close_series.iloc[-1])
        if cmp_price is not None and cmp_price > 0:
            current_close = float(cmp_price)
        result["current_close"] = current_close

        # EMA20 / EMA50
        ema20 = float(
            close_series.ewm(span=cfg.ema_fast_period, adjust=False).mean().iloc[-1]
        )
        ema50 = (
            float(
                close_series.ewm(span=cfg.ema_slow_period, adjust=False).mean().iloc[-1]
            )
            if len(candles) >= cfg.ema_slow_period
            else None
        )

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

        # Determine trading zone: where is price relative to EMA20/EMA50?
        if ema50 is not None and current_close > ema50:
            trading_zone = "above_ema50"
        elif current_close > ema20:
            trading_zone = "above_ema20"
        elif current_close > ema20 * 0.98:
            trading_zone = "at_ema20"
        else:
            trading_zone = "below_ema20"

        # Support/resistance zones via swing clustering
        support_zones = self._find_support_zones(low_series, atr14, cfg.range_analysis_days)
        resistance_zones = self._find_resistance_zones(high_series, atr14, cfg.range_analysis_days)

        nearest_support = support_zones[-1] if support_zones else current_close
        nearest_resistance = resistance_zones[-1] if resistance_zones else current_close

        # Determine where old levels sit relative to current market
        old_levels_sorted = sorted(
            [l for l in current_levels if l.get("price")],
            key=lambda x: x["price"],
            reverse=True,
        )
        old_e1 = old_levels_sorted[0]["price"] if len(old_levels_sorted) > 0 else None
        old_e3 = old_levels_sorted[-1]["price"] if len(old_levels_sorted) >= 3 else None

        # Determine revision reason
        if old_e1 and old_e1 > nearest_resistance * 1.1:
            revision_reason = "Market repriced lower"
            use_zone = nearest_resistance
        elif old_e1 and old_e1 < nearest_support * 0.9:
            revision_reason = "Market repriced higher"
            use_zone = nearest_support
        elif old_e3 and old_e3 > current_close:
            revision_reason = "Support structure changed"
            use_zone = nearest_support
        elif old_e1 and old_e1 > current_close * 1.3:
            revision_reason = "Trading range shifted"
            use_zone = current_close
        else:
            revision_reason = "Swing structure changed"
            use_zone = current_close

        result["revision_reason"] = revision_reason
        result["style"] = style
        result["ema20"] = round(ema20, 2)
        result["ema50"] = round(ema50, 2) if ema50 else None
        result["trading_zone"] = trading_zone
        result["nearest_support"] = round(nearest_support, 2)
        result["nearest_resistance"] = round(nearest_resistance, 2)

        # Calculate suggested levels — spacing varies by revision style
        atr_mult, zone_mult = _STYLE_MULTIPLIERS.get(
            style, _STYLE_MULTIPLIERS["balanced"]
        )
        gap = max(atr14 * atr_mult, use_zone * zone_mult)
        suggested_e1 = round(use_zone * 1.0, 2)
        suggested_e2 = round(use_zone - gap, 2)
        suggested_e3 = round(use_zone - gap * 2, 2)

        result["gap"] = round(gap, 2)
        result["suggested_entry1"] = suggested_e1
        result["suggested_entry2"] = suggested_e2
        result["suggested_entry3"] = suggested_e3

        # Thesis break price — delegate to canonical ThesisBreakService
        from core.services.thesis_break import get_thesis_break_service

        thesis_svc = get_thesis_break_service()
        thesis_break = thesis_svc.calculate(symbol, suggested_e3, candles)
        result["thesis_break_price"] = round(thesis_break, 2) if thesis_break else None

        logger.info(
            f"Market structure revision generated for {symbol}: "
            f"E1={suggested_e1} E2={suggested_e2} E3={suggested_e3} "
            f"thesis_break={thesis_break} reason={revision_reason}"
        )

        return result

    def _find_support_zones(
        self, low_series: pd.Series, atr: float, lookback: int
    ) -> List[float]:
        """Find clustered support levels from swing lows within lookback period."""
        lows = low_series.tail(lookback).values
        return self._cluster_levels(lows, atr * 1.5)

    def _find_resistance_zones(
        self, high_series: pd.Series, atr: float, lookback: int
    ) -> List[float]:
        """Find clustered resistance levels from swing highs within lookback period."""
        highs = high_series.tail(lookback).values
        return self._cluster_levels(highs, atr * 1.5)

    def _cluster_levels(self, values, threshold: float) -> List[float]:
        """Group nearby values into clusters and return cluster means sorted ascending."""
        if len(values) == 0:
            return []

        sorted_vals = sorted(values)
        clusters: List[List[float]] = [[sorted_vals[0]]]

        for v in sorted_vals[1:]:
            if abs(v - clusters[-1][-1]) <= threshold:
                clusters[-1].append(v)
            else:
                clusters.append([v])

        # Return mean of each cluster
        return [round(sum(c) / len(c), 2) for c in clusters if len(c) >= 2]


_market_structure_revision_service: MarketStructureRevisionService | None = None


def get_market_structure_revision_service() -> MarketStructureRevisionService:
    global _market_structure_revision_service
    if _market_structure_revision_service is None:
        _market_structure_revision_service = MarketStructureRevisionService()
    return _market_structure_revision_service
