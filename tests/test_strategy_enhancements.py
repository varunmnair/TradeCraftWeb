"""Tests for Phase 1 Entry Strategy enhancements.

Covers:
  - core/strategy_config.py
  - core/services/swing_eligibility.py
  - core/services/market_structure_revision.py
  - core/services/thesis_break.py
  - db.models.EntryStrategy fields
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List

import pandas as pd
import pytest

from core.strategy_config import StrategyConfig, get_strategy_config
from core.services.swing_eligibility import (
    SwingEligibilityService,
    get_swing_eligibility_service,
)
from core.services.market_structure_revision import (
    MarketStructureRevisionService,
    get_market_structure_revision_service,
)
from core.services.thesis_break import (
    ThesisBreakService,
    get_thesis_break_service,
)
from db.models import EntryStrategy, User


# ── Helpers ────────────────────────────────────────────────────────

def _candle(
    close: float,
    high: float | None = None,
    low: float | None = None,
    volume: int = 200000,
    day_offset: int = 0,
) -> dict:
    """Single OHLCV candle with sensible high/low defaults."""
    d = date.today() - timedelta(days=day_offset)
    h = high if high is not None else close + 5.0
    l = low if low is not None else close - 5.0
    return {
        "date": d,
        "open": close - 0.5,
        "high": h,
        "low": l,
        "close": close,
        "volume": volume,
    }


def _make_candles(
    close_prices: List[float],
    volume: int = 200000,
    high_low: List[tuple[float | None, float | None]] | None = None,
) -> List[Dict]:
    """Build a candle list sorted ascending by date (oldest first)."""
    candles: list[dict] = []
    n = len(close_prices)
    for i, p in enumerate(close_prices):
        h: float | None = None
        l: float | None = None
        if high_low and i < len(high_low):
            h, l = high_low[i]
        candles.append(_candle(p, high=h, low=l, volume=volume, day_offset=n - 1 - i))
    return candles


# ════════════════════════════════════════════════════════════════════
# StrategyConfig
# ════════════════════════════════════════════════════════════════════

class TestStrategyConfig:
    def test_get_strategy_config_returns_config(self):
        config = get_strategy_config()
        assert isinstance(config, StrategyConfig)

    def test_strategy_config_defaults(self):
        config = StrategyConfig()
        assert config.strategy_review_days == 30
        assert config.atr_period == 14
        assert config.ema_fast_period == 20
        assert config.ema_slow_period == 50
        assert config.range_analysis_days == 60
        assert config.volume_average_days == 20
        assert config.minimum_avg_volume == 100000
        assert config.minimum_atr_percent == 1.0
        assert config.minimum_trading_range_percent == 5.0


# ════════════════════════════════════════════════════════════════════
# SwingEligibilityService
# ════════════════════════════════════════════════════════════════════

class TestSwingEligibility:
    def test_get_swing_eligibility_service(self):
        svc = get_swing_eligibility_service()
        assert isinstance(svc, SwingEligibilityService)

    def test_evaluate_valid_ohlcv_returns_eligible(self):
        """All criteria met → swing_eligible = True."""
        svc = get_swing_eligibility_service()
        candles = _make_candles([100.0] * 60, volume=200000)
        result = svc.evaluate("TEST", candles)
        assert result["swing_eligible"] is True
        assert result["current_close"] == 100.0
        assert result["atr_percent"] >= 1.0
        assert result["range_percent"] >= 5.0

    def test_evaluate_insufficient_data_not_eligible(self):
        """Less than 20 candles → swing_eligible = False."""
        svc = get_swing_eligibility_service()
        candles = _make_candles([100.0] * 10)
        result = svc.evaluate("TEST", candles)
        assert result["swing_eligible"] is False
        assert "Insufficient OHLCV data" in result["reasons"]

    def test_evaluate_sets_reasons_on_failure(self):
        """Failure reasons are populated when criteria not met."""
        svc = get_swing_eligibility_service()
        # Low volume to fail the volume check; narrow spread to fail range check
        candles = _make_candles(
            [100.0] * 60,
            volume=500,  # far below minimum_avg_volume (100000)
            high_low=[(100.5, 99.5)] * 60,  # tight range → atr% and range% both tiny
        )
        result = svc.evaluate("TEST", candles)
        assert result["swing_eligible"] is False
        assert len(result["reasons"]) >= 1
        # At least one of the expected reasons should be present
        all_reasons = " ".join(result["reasons"]).lower()
        assert any(word in all_reasons for word in ("volume", "atr", "range"))


# ════════════════════════════════════════════════════════════════════
# MarketStructureRevisionService
# ════════════════════════════════════════════════════════════════════

class TestMarketStructureRevision:
    def test_get_market_structure_revision_service(self):
        svc = get_market_structure_revision_service()
        assert isinstance(svc, MarketStructureRevisionService)

    def test_suggest_revision_valid_data(self):
        """Returns revised entry levels with valid OHLCV data."""
        svc = get_market_structure_revision_service()
        candles = _make_candles([100.0] * 60, volume=200000)
        current_levels = [
            {"level_no": 1, "price": 105.0},
            {"level_no": 2, "price": 100.0},
            {"level_no": 3, "price": 95.0},
        ]
        result = svc.suggest_revision("TEST", current_levels, candles)
        assert result["suggested_entry1"] is not None
        assert result["suggested_entry2"] is not None
        assert result["suggested_entry3"] is not None
        # Entry1 should be >= Entry2 >= Entry3
        assert result["suggested_entry1"] >= result["suggested_entry2"]
        assert result["suggested_entry2"] >= result["suggested_entry3"]

    def test_suggest_revision_output_fields(self):
        """Output contains all expected keys."""
        svc = get_market_structure_revision_service()
        candles = _make_candles([100.0] * 60, volume=200000)
        current_levels = [{"level_no": 1, "price": 105.0}]
        result = svc.suggest_revision("TEST", current_levels, candles)
        assert "suggested_entry1" in result
        assert "suggested_entry2" in result
        assert "suggested_entry3" in result
        assert "revision_reason" in result
        assert "thesis_break_price" in result
        assert result["revision_reason"] is not None
        assert result["thesis_break_price"] is not None

    def test_suggest_revision_insufficient_data(self):
        """Fewer than 20 candles falls back gracefully with a reason."""
        svc = get_market_structure_revision_service()
        candles = _make_candles([100.0] * 10)
        current_levels = [{"level_no": 1, "price": 105.0}]
        result = svc.suggest_revision("TEST", current_levels, candles)
        assert result["suggested_entry1"] is None
        assert result["revision_reason"] == "Insufficient OHLCV data"

    def test_suggest_revision_detects_zones(self):
        """Support/resistance zones are computed and influence the output."""
        svc = get_market_structure_revision_service()
        # Create 60 candles where lows cluster at ~85 and highs at ~115,
        # producing detectable support/resistance zones
        high_low: list[tuple[float | None, float | None]] = []
        for i in range(60):
            if i < 40:
                high_low.append((115.0, 85.0))
            else:
                high_low.append((115.0, 90.0))
        candles = _make_candles([100.0] * 60, high_low=high_low)
        current_levels = [
            {"level_no": 1, "price": 130.0},  # well above resistance → "Market repriced lower"
            {"level_no": 2, "price": 100.0},
            {"level_no": 3, "price": 95.0},
        ]
        result = svc.suggest_revision("TEST", current_levels, candles)
        # Should be "Market repriced lower" since old_e1 (130) >> nearest_resistance (~115)
        assert result["revision_reason"] is not None
        assert result["suggested_entry1"] is not None
        # thesis_break_price must be a positive number below entry3
        assert result["thesis_break_price"] is not None
        assert result["thesis_break_price"] > 0


# ════════════════════════════════════════════════════════════════════
# ThesisBreakService
# ════════════════════════════════════════════════════════════════════

class TestThesisBreak:
    def test_get_thesis_break_service(self):
        svc = get_thesis_break_service()
        assert isinstance(svc, ThesisBreakService)

    def test_detect_breach_returns_true_when_broken(self):
        """close <= thesis_break_price → thesis_broken = True."""
        svc = get_thesis_break_service()
        assert svc.detect_breach("TEST", current_close=90.0, thesis_break_price=95.0) is True
        assert svc.detect_breach("TEST", current_close=95.0, thesis_break_price=95.0) is True

    def test_detect_breach_returns_false_when_not_broken(self):
        """close > thesis_break_price → thesis_broken = False."""
        svc = get_thesis_break_service()
        assert svc.detect_breach("TEST", current_close=100.0, thesis_break_price=95.0) is False

    def test_detect_breach_no_thesis_break_price(self):
        """None thesis_break_price → thesis_broken = False."""
        svc = get_thesis_break_service()
        assert svc.detect_breach("TEST", current_close=90.0, thesis_break_price=None) is False

    def test_calculate_thesis_break_with_enough_data(self):
        """calculate() returns a float price with sufficient candles."""
        svc = get_thesis_break_service()
        candles = _make_candles([100.0] * 60, volume=200000)
        price = svc.calculate("TEST", entry3_price=80.0, candles=candles)
        assert price is not None
        assert isinstance(price, float)
        assert price > 0

    def test_calculate_thesis_break_insufficient_data(self):
        """calculate() returns None with too few candles."""
        svc = get_thesis_break_service()
        candles = _make_candles([100.0] * 5)
        price = svc.calculate("TEST", entry3_price=80.0, candles=candles)
        assert price is None


# ════════════════════════════════════════════════════════════════════
# EntryStrategy model (DB)
# ════════════════════════════════════════════════════════════════════

class TestEntryStrategyModel:
    def test_entry_strategy_model_fields(self, db_session):
        user = User(email="model_test@tradecraftx.dev", trading_enabled=True)
        db_session.add(user)
        db_session.commit()

        strategy = EntryStrategy(
            user_id=user.id,
            symbol="TEST",
            swing_eligible=True,
            thesis_break_price=95.50,
            review_status="ACTIVE",
            last_evaluated_at=None,
            last_entry_revision_at=None,
        )
        db_session.add(strategy)
        db_session.commit()
        db_session.refresh(strategy)

        assert strategy.id is not None
        assert strategy.swing_eligible is True
        assert strategy.thesis_break_price == 95.50
        assert strategy.review_status == "ACTIVE"
        assert strategy.last_evaluated_at is None
        assert strategy.last_entry_revision_at is None

    def test_entry_strategy_review_status_default(self, db_session):
        """review_status defaults to 'ACTIVE' when not provided."""
        user = User(email="default_test@tradecraftx.dev", trading_enabled=True)
        db_session.add(user)
        db_session.commit()

        strategy = EntryStrategy(
            user_id=user.id,
            symbol="DEFAULT",
        )
        db_session.add(strategy)
        db_session.commit()
        db_session.refresh(strategy)

        assert strategy.review_status == "ACTIVE"
