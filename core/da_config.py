from __future__ import annotations

import copy
import threading
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    # Legacy sell-side fields (deprecated, kept for backward compat)
    "minimum_da_net_profit": 100,
    "default_sell_offset": 0.01,
    "minimum_volume_threshold": 10000,
    "da_range_analysis_days": 10,
    "high_confidence_qty_pct": 50,
    "medium_confidence_qty_pct": 40,
    "low_confidence_qty_pct": 30,
    "no_recommendation_min_score": 40,
    "confidence_high_threshold": 85,
    "confidence_medium_threshold": 60,
    "confidence_low_threshold": 40,
    # System-driven DA Buy config
    "minimum_da_decline_pct": 3,
    "max_da_legs": 2,
    "min_da_cost_pct": 0.3,
    "min_da_net_benefit": 100,
    "da_lookback_days": 20,
}

_da_config: dict[str, Any] = {}
_da_config_lock = threading.Lock()


def get_da_config() -> dict[str, Any]:
    global _da_config
    if not _da_config:
        with _da_config_lock:
            if not _da_config:
                _da_config = copy.deepcopy(DEFAULT_CONFIG)
    return copy.deepcopy(_da_config)


def update_da_config(updates: dict[str, Any]) -> dict[str, Any]:
    global _da_config
    valid_keys = set(DEFAULT_CONFIG.keys())
    with _da_config_lock:
        for key, value in updates.items():
            if key in valid_keys:
                _da_config[key] = value
        return copy.deepcopy(_da_config)


def reset_da_config() -> None:
    global _da_config
    with _da_config_lock:
        _da_config = copy.deepcopy(DEFAULT_CONFIG)
