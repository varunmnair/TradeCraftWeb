"""Application-level configuration for entry strategy enhancement features."""

from __future__ import annotations

import os


class StrategyConfig:
    """Configurable parameters for strategy review lifecycle, swing eligibility,
    market structure revision, and thesis break calculations.

    All values can be overridden via environment variables with STRATEGY_ prefix.
    """

    strategy_review_days: int = int(os.getenv("STRATEGY_REVIEW_DAYS", "30"))
    atr_period: int = int(os.getenv("STRATEGY_ATR_PERIOD", "14"))
    ema_fast_period: int = int(os.getenv("STRATEGY_EMA_FAST", "20"))
    ema_slow_period: int = int(os.getenv("STRATEGY_EMA_SLOW", "50"))
    range_analysis_days: int = int(os.getenv("STRATEGY_RANGE_DAYS", "60"))
    volume_average_days: int = int(os.getenv("STRATEGY_VOLUME_DAYS", "20"))
    minimum_avg_volume: int = int(os.getenv("STRATEGY_MIN_VOLUME", "100000"))
    minimum_atr_percent: float = float(os.getenv("STRATEGY_MIN_ATR_PCT", "1.0"))
    minimum_trading_range_percent: float = float(os.getenv("STRATEGY_MIN_RANGE_PCT", "5.0"))
    max_below_entry3_percent: float = float(os.getenv("STRATEGY_MAX_BELOW_E3_PCT", "10.0"))
    entry_opportunity_window_pct: float = float(os.getenv("STRATEGY_ENTRY_OPPTY_WIN_PCT", "10.0"))
    # System-driven DA Buy config
    minimum_da_decline_pct: float = float(os.getenv("DA_MIN_DECLINE_PCT", "3.0"))
    tranche_completion_pct: float = float(os.getenv("DA_TRANCHE_COMPLETION_PCT", "8.0"))
    max_da_legs: int = int(os.getenv("DA_MAX_LEGS", "2"))
    min_da_cost_pct: float = float(os.getenv("DA_MIN_COST_PCT", "0.3"))
    min_da_net_benefit: float = float(os.getenv("DA_MIN_NET_BENEFIT", "100"))
    da_lookback_days: int = int(os.getenv("DA_LOOKBACK_DAYS", "20"))


_config: StrategyConfig | None = None


def get_strategy_config() -> StrategyConfig:
    global _config
    if _config is None:
        _config = StrategyConfig()
    return _config
