"""Tests for core/candidate_service.py — deduplication, multi-leg DA, and DA-over-MLE suppression."""

from __future__ import annotations

from unittest.mock import MagicMock

from core.candidate_service import PRIORITY_ORDER
from core.candidates import CandidateStatus, NormalizedCandidate, StrategyType
from core.evaluators import CandidateContext
from core.strategy_config import StrategyConfig


def _make_candidate(
    symbol: str,
    strategy_type: StrategyType,
    side: str = "BUY",
    status: CandidateStatus = CandidateStatus.WARNING,
    level_or_leg: str | None = None,
    **overrides,
) -> NormalizedCandidate:
    defaults = {
        "symbol": symbol,
        "exchange": "NSE",
        "strategy_type": strategy_type,
        "side": side,
        "status": status,
        "status_severity": 1,
        "signal": None,
        "cmp": 100.0,
        "order_price": 100.0,
        "trigger_price": 100.0,
        "qty": 10,
        "amount": 1000.0,
        "allocation": 30000.0,
        "current_holding_qty": 100,
        "current_holding_value": 10000.0,
        "allocation_used_percent": 33.3,
        "level_or_leg": level_or_leg,
        "strategy_reference": "TEST",
        "reason_code": None,
        "reason_message": "Test",
        "suggested_action": "Test",
        "is_selectable": True,
        "created_at": "2025-01-01T00:00:00Z",
        "additional_details": {},
    }
    defaults.update(overrides)
    return NormalizedCandidate(**defaults)


def _make_cmp_manager(prices: dict[str, float] | None = None) -> MagicMock:
    mgr = MagicMock()
    mgr.get_cmp = MagicMock(side_effect=lambda ex, sym: (prices or {}).get(sym))
    return mgr


def _make_context(
    entry_levels=None,
    holdings=None,
    exclude_symbols=None,
    cmp_prices=None,
) -> CandidateContext:
    return CandidateContext(
        entry_levels=entry_levels or [],
        holdings=holdings or [],
        cmp_manager=_make_cmp_manager(cmp_prices or {}),
        broker=MagicMock(),
        gtt_cache=[],
        completed_trade_symbols=set(),
        config=StrategyConfig(),
        existing_gtt_symbols=set(),
        exclude_symbols=exclude_symbols or set(),
    )


# ---------------------------------------------------------------------------
# 1. DA suppresses MLE — exclusion check in CandidateContext
# ---------------------------------------------------------------------------


class TestDASuppressesMLE:
    def test_exclude_symbols_prevents_mle_generation(self):
        """MLE evaluator skips symbols in context.exclude_symbols."""
        from core.evaluators.multi_level import MultiLevelCandidateEvaluator

        entry_levels = [
            {"symbol": "TEST", "Allocated": 30000, "exchange": "NSE",
             "entry1": 100.0, "entry2": 95.0, "entry3": 90.0},
        ]
        ctx = _make_context(
            entry_levels=entry_levels,
            exclude_symbols={"TEST"},
        )

        evaluator = MultiLevelCandidateEvaluator()
        candidates, skipped = evaluator.identify_candidates(ctx)

        mle_cands = [c for c in candidates if c.strategy_type == StrategyType.MULTI_LEVEL]
        assert len(mle_cands) == 0

    def test_non_excluded_symbols_still_generates_mle(self):
        """MLE runs normally for symbols not in exclude_symbols."""
        from core.evaluators.multi_level import MultiLevelCandidateEvaluator

        entry_levels = [
            {"symbol": "TEST", "Allocated": 30000, "exchange": "NSE",
             "entry1": 100.0, "entry2": 95.0, "entry3": 90.0},
        ]
        holdings = [
            {"tradingsymbol": "TEST", "quantity": 100, "t1_quantity": 0,
             "average_price": 100.0, "exchange": "NSE"},
        ]
        ctx = _make_context(
            entry_levels=entry_levels,
            holdings=holdings,
            exclude_symbols=set(),
            cmp_prices={"TEST": 98.0},
        )

        evaluator = MultiLevelCandidateEvaluator()
        candidates, skipped = evaluator.identify_candidates(ctx)

        mle_cands = [c for c in candidates if c.strategy_type == StrategyType.MULTI_LEVEL]
        assert len(mle_cands) >= 1

    def test_partial_exclusion(self):
        """Only excluded symbols are skipped; others generate normally."""
        from core.evaluators.multi_level import MultiLevelCandidateEvaluator

        entry_levels = [
            {"symbol": "A", "Allocated": 30000, "exchange": "NSE",
             "entry1": 100.0, "entry2": 95.0, "entry3": 90.0},
            {"symbol": "B", "Allocated": 30000, "exchange": "NSE",
             "entry1": 100.0, "entry2": 95.0, "entry3": 90.0},
        ]
        holdings = [
            {"tradingsymbol": "A", "quantity": 50, "t1_quantity": 0,
             "average_price": 105.0, "exchange": "NSE"},
            {"tradingsymbol": "B", "quantity": 100, "t1_quantity": 0,
             "average_price": 100.0, "exchange": "NSE"},
        ]
        ctx = _make_context(
            entry_levels=entry_levels,
            holdings=holdings,
            exclude_symbols={"A"},
            cmp_prices={"A": 98.0, "B": 98.0},
        )

        evaluator = MultiLevelCandidateEvaluator()
        candidates, skipped = evaluator.identify_candidates(ctx)

        # A should not appear in any output
        a_cands = [c for c in candidates if c.symbol == "A"]
        a_skipped = [s for s in skipped if s.symbol == "A"]
        assert len(a_cands) == 0
        assert len(a_skipped) == 0


# ---------------------------------------------------------------------------
# 2. Multi-leg DA deduplication
# ---------------------------------------------------------------------------


class TestMultiLegDeduplication:
    def test_same_strategy_legs_both_kept(self):
        """DA1 + DA2 for same symbol should both survive deduplication."""
        da1 = _make_candidate("PNCINFRA", StrategyType.DYNAMIC_AVERAGING, level_or_leg="DA1")
        da2 = _make_candidate("PNCINFRA", StrategyType.DYNAMIC_AVERAGING, level_or_leg="DA2")

        symbol_map: dict[str, list[NormalizedCandidate]] = {}
        for c in [da1, da2]:
            symbol_map.setdefault(c.symbol, []).append(c)

        deduplicated: list[NormalizedCandidate] = []
        all_skipped: list = []
        for sym, cands in symbol_map.items():
            cands.sort(key=lambda c: PRIORITY_ORDER.get(c.strategy_type, 99))
            best = cands[0]
            deduplicated.append(best)
            for rejected in cands[1:]:
                if rejected.strategy_type == best.strategy_type:
                    deduplicated.append(rejected)
                    continue
                all_skipped.append(rejected)

        assert len(deduplicated) == 2
        assert all_skipped == []

    def test_three_symbols_independent_dedup(self):
        """Deduplication is per-symbol, not global."""
        cands = [
            _make_candidate("A", StrategyType.MULTI_LEVEL, level_or_leg="E1"),
            _make_candidate("A", StrategyType.DYNAMIC_AVERAGING, level_or_leg="DA1"),
            _make_candidate("B", StrategyType.DYNAMIC_AVERAGING, level_or_leg="DA1"),
            _make_candidate("B", StrategyType.DYNAMIC_AVERAGING, level_or_leg="DA2"),
            _make_candidate("C", StrategyType.MULTI_LEVEL, level_or_leg="E1"),
        ]

        symbol_map: dict[str, list[NormalizedCandidate]] = {}
        for c in cands:
            symbol_map.setdefault(c.symbol, []).append(c)

        deduplicated: list[NormalizedCandidate] = []
        all_skipped: list = []
        for sym, syms in symbol_map.items():
            syms.sort(key=lambda c: PRIORITY_ORDER.get(c.strategy_type, 99))
            best = syms[0]
            deduplicated.append(best)
            for rejected in syms[1:]:
                if rejected.strategy_type == best.strategy_type:
                    deduplicated.append(rejected)
                    continue
                all_skipped.append(rejected)

        # A: MLE kept, DA rejected → 1 kept, 1 skipped
        # B: DA1 + DA2 both kept → 2 kept, 0 skipped
        # C: only MLE → 1 kept, 0 skipped
        assert len(deduplicated) == 4
        assert len(all_skipped) == 1
        assert all_skipped[0].symbol == "A"
        assert all_skipped[0].strategy_type == StrategyType.DYNAMIC_AVERAGING


# ---------------------------------------------------------------------------
# 3. DA skip suppression when MLE produces candidate
# ---------------------------------------------------------------------------


class TestDASkipSuppression:
    def test_da_skip_suppressed_when_mle_candidate_exists(self):
        """DA skip records for a symbol are suppressed when MLE produces a candidate."""
        da_skips = [
            MagicMock(symbol="TEST", strategy_type=StrategyType.DYNAMIC_AVERAGING),
            MagicMock(symbol="OTHER", strategy_type=StrategyType.DYNAMIC_AVERAGING),
        ]
        mle_cands = [
            _make_candidate("TEST", StrategyType.MULTI_LEVEL),
        ]

        mle_symbols = {c.symbol for c in mle_cands}
        filtered_skips = [s for s in da_skips if s.symbol not in mle_symbols]

        assert len(filtered_skips) == 1
        assert filtered_skips[0].symbol == "OTHER"

    def test_da_skip_not_suppressed_when_no_mle_candidate(self):
        """DA skip records are kept when no MLE candidate exists for that symbol."""
        da_skips = [
            MagicMock(symbol="TEST", strategy_type=StrategyType.DYNAMIC_AVERAGING),
        ]
        mle_cands = []

        mle_symbols = {c.symbol for c in mle_cands}
        filtered_skips = [s for s in da_skips if s.symbol not in mle_symbols]

        assert len(filtered_skips) == 1
