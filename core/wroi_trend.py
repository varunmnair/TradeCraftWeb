"""WROI trend calculation for holdings capital efficiency analysis."""

from __future__ import annotations

import logging
from typing import Dict, List

logger = logging.getLogger("tradecraftx.wroi_trend")

TRADING_SESSIONS_NEEDED = 6


def compute_wroi_trends(
    holdings: List[Dict],
    ohlcv_by_symbol: Dict[str, List[Dict]],
    total_invested: float,
) -> Dict[str, str]:
    """Compute WROI capital efficiency trend for each holding symbol.

    Args:
        holdings: List of analyzed holding dicts with keys:
                  symbol, quantity, average_price, invested, age, weighted_roi.
        ohlcv_by_symbol: Dict mapping symbol to list of OHLCV candles
                         (sorted by trade_date ascending). Each candle
                         must have a 'close' key.
        total_invested: Sum of all holdings' invested values.

    Returns:
        Dict mapping symbol to trend value:
        "STRONG_UP", "UP", "STRONG_DOWN", "DOWN", "NEUTRAL", or "NA".
    """
    if not holdings or total_invested <= 0:
        logger.debug("No holdings or total_invested is zero, returning empty trends")
        return {}

    holding_by_symbol: Dict[str, Dict] = {}
    for h in holdings:
        sym = h.get("symbol", "").replace("-BE", "").replace("#", "").upper()
        holding_by_symbol[sym] = h

    logger.info(
        f"Computing WROI trends for {len(ohlcv_by_symbol)} symbols "
        f"(total_invested={total_invested:.2f})"
    )

    result: Dict[str, str] = {}
    total_weight = 0.0

    for symbol in sorted(ohlcv_by_symbol):
        holding = holding_by_symbol.get(symbol)
        if not holding:
            logger.debug(f"Holding not found for {symbol}, skipping")
            result[symbol] = "NA"
            continue

        close_prices = _get_close_prices(ohlcv_by_symbol[symbol])
        if len(close_prices) < TRADING_SESSIONS_NEEDED:
            logger.debug(
                f"Insufficient OHLCV for {symbol}: "
                f"got {len(close_prices)}, need {TRADING_SESSIONS_NEEDED}"
            )
            result[symbol] = "NA"
            continue

        age = holding.get("age")
        if age is None:
            logger.debug(f"No age data for {symbol}, skipping")
            result[symbol] = "NA"
            continue

        qty = holding.get("quantity", 0)
        avg_price = holding.get("average_price", 0)
        invested = holding.get("invested", 0)

        if qty == 0 or avg_price == 0 or invested <= 0:
            logger.debug(
                f"Invalid holding data for {symbol} "
                f"(qty={qty}, avg_price={avg_price}, invested={invested})"
            )
            result[symbol] = "NA"
            continue

        recent_prices = close_prices[-TRADING_SESSIONS_NEEDED:]

        wroi_values: List[float] = []
        for day_index, historical_close in enumerate(recent_prices):
            days_back = TRADING_SESSIONS_NEEDED - 1 - day_index

            profit = (qty * historical_close) - invested
            roi = profit / invested
            historical_age = max(1, age - days_back)
            roi_per_day = roi / historical_age
            portfolio_weight = invested / total_invested
            wroi = roi_per_day * portfolio_weight
            wroi_values.append(wroi)

        up_moves = 0
        down_moves = 0

        for i in range(1, len(wroi_values)):
            if wroi_values[i] > wroi_values[i - 1]:
                up_moves += 1
            elif wroi_values[i] < wroi_values[i - 1]:
                down_moves += 1

        if up_moves == 5:
            trend = "STRONG_UP"
        elif up_moves == 4:
            trend = "UP"
        elif down_moves == 5:
            trend = "STRONG_DOWN"
        elif down_moves == 4:
            trend = "DOWN"
        else:
            trend = "NEUTRAL"

        result[symbol] = trend
        total_weight += invested
        logger.debug(
            f"WROI trend for {symbol}: {trend} "
            f"(up={up_moves}, down={down_moves}, age={age}, invested={invested:.0f})"
        )

    logger.info(f"Computed WROI trends for {len(result)} symbols (total analyzed={total_weight:.0f})")
    return result


def _get_close_prices(candles: List[Dict]) -> List[float]:
    """Extract close prices from OHLCV candles, sorted by date ascending."""
    prices = []
    for c in candles:
        close_val = c.get("close")
        if close_val is not None:
            prices.append(float(close_val))
    return prices
