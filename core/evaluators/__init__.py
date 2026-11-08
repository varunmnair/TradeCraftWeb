"""Base candidate evaluator and shared context for the entry candidate pipeline."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.candidates import NormalizedCandidate, SkippedCandidate, StrategyType
    from core.cmp import CMPManager
    from core.strategy_config import StrategyConfig


def tranche_completion_threshold(
    per_level_allocation: float, current_cmp: float, tranche_completion_pct: float = 8.0
) -> float:
    """A tranche is effectively complete when the remaining gap is <= this threshold.

    Handles quantity rounding, high stock prices, partial manual selling,
    and inability to perfectly deploy exact tranche amounts.
    """
    return max(per_level_allocation * tranche_completion_pct / 100, current_cmp)


def validate_entry_level_order(
    entry_prices: list[tuple[int, float]],
) -> str | None:
    """Validate that entry levels are in strictly descending price order.

    Returns None if valid, or a technical details string describing the violation.
    """
    if len(entry_prices) < 2:
        return None

    sorted_entries = sorted(entry_prices, key=lambda x: x[0])
    for i in range(len(sorted_entries) - 1):
        _, price_a = sorted_entries[i]
        _, price_b = sorted_entries[i + 1]
        if price_a <= price_b:
            labels = [f"E{n}={p}" for n, p in sorted_entries]
            return f"Entry order invalid: {', '.join(labels)}"
    return None


@dataclass
class CandidateContext:
    """Data bundle passed to evaluators. Built once per candidate generation run."""

    entry_levels: list[dict]
    holdings: list[dict]
    cmp_manager: CMPManager
    broker: object
    gtt_cache: list[dict]
    completed_trade_symbols: set[str]
    config: StrategyConfig
    existing_gtt_symbols: set[str] = field(default_factory=set)
    exclude_symbols: set[str] = field(default_factory=set)

    def get_holdings_map(self) -> dict[str, dict]:
        return {h["tradingsymbol"].replace("#", "").replace("-BE", ""): h for h in self.holdings}

    def get_entry_levels_map(self) -> dict[str, dict]:
        return {
            str(e.get("symbol", "")).strip().upper(): e
            for e in self.entry_levels
            if isinstance(e.get("symbol"), str) and e.get("symbol", "").strip()
        }


class BaseCandidateEvaluator(ABC):
    @abstractmethod
    def identify_candidates(
        self, context: CandidateContext
    ) -> tuple[list[NormalizedCandidate], list[SkippedCandidate]]:
        """Run candidate identification and return (ready/warning/review candidates, skipped items)."""
        ...

    @property
    @abstractmethod
    def strategy_type(self) -> StrategyType: ...
