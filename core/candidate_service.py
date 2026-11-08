"""Entry candidate service — orchestrates evaluators, deduplicates, and ranks candidates."""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime
from typing import TYPE_CHECKING

from core.candidates import (
    CandidateResult,
    CandidateStatus,
    CandidateSummary,
    NormalizedCandidate,
    ReasonCode,
    SkippedCandidate,
    StrategyType,
)
from core.evaluators import CandidateContext
from core.evaluators.dynamic_avg import DynamicAveragingCandidateEvaluator
from core.evaluators.multi_level import MultiLevelCandidateEvaluator
from core.strategy_config import get_strategy_config

if TYPE_CHECKING:
    from core.cmp import CMPManager

logger = logging.getLogger(__name__)

PRIORITY_ORDER = {
    StrategyType.MULTI_LEVEL: 0,
    StrategyType.SIP: 1,
    StrategyType.DYNAMIC_AVERAGING: 2,
}


class EntryCandidateService:
    """Runs all evaluators, merges results, deduplicates per-symbol, and ranks."""

    def __init__(
        self,
        broker,
        cmp_manager: CMPManager,
        holdings: list[dict],
        entry_levels: list[dict],
        gtt_cache: list[dict] | None = None,
    ):
        self.broker = broker
        self.cmp_manager = cmp_manager
        self.holdings = holdings
        self.entry_levels = entry_levels
        self.gtt_cache = gtt_cache or []
        self.config = get_strategy_config()

        self._evaluators = [
            MultiLevelCandidateEvaluator(),
            DynamicAveragingCandidateEvaluator(),
        ]

    def _build_context(self) -> CandidateContext:
        from datetime import datetime as _dt

        completed_trade_symbols: set[str] = set()
        try:
            trades = self.broker.trades()
            today = _dt.now().date()
            for trade in trades or []:
                fill_ts = trade.get("fill_timestamp")
                if fill_ts and hasattr(fill_ts, "date") and fill_ts.date() == today:
                    if trade.get("transaction_type") == "BUY":
                        sym = trade.get("tradingsymbol", "").upper()
                        if sym:
                            completed_trade_symbols.add(sym)
        except Exception:
            logger.warning("Could not fetch trades for duplicate detection", exc_info=True)

        existing_gtt_symbols: set[str] = set()
        for gtt in self.gtt_cache:
            tsym = gtt.get("tradingsymbol", "").upper()
            if tsym:
                existing_gtt_symbols.add(tsym)

        return CandidateContext(
            entry_levels=self.entry_levels,
            holdings=self.holdings,
            cmp_manager=self.cmp_manager,
            broker=self.broker,
            gtt_cache=self.gtt_cache,
            completed_trade_symbols=completed_trade_symbols,
            config=self.config,
            existing_gtt_symbols=existing_gtt_symbols,
        )

    def generate(self) -> CandidateResult:
        """Two-phase evaluation: DA first (cost-basis optimization), then MLE (accumulation).

        Symbols with meaningful DA candidates suppress MLE generation.
        DA skip records are suppressed when MLE produces a candidate for the same symbol.
        """
        context = self._build_context()

        all_candidates: list[NormalizedCandidate] = []
        all_skipped: list[SkippedCandidate] = []

        # Phase 1: DA first — identifies cost-basis optimization opportunities
        da_evaluator = None
        for evaluator in self._evaluators:
            if isinstance(evaluator, DynamicAveragingCandidateEvaluator):
                da_evaluator = evaluator
                break

        if da_evaluator is not None:
            try:
                da_cands, da_skips = da_evaluator.identify_candidates(context)
                all_candidates.extend(da_cands)
                all_skipped.extend(da_skips)
            except Exception:
                logger.error("DA evaluator failed", exc_info=True)

        # Phase 2: Remaining evaluators — with DA exclusion
        da_symbols = {c.symbol for c in all_candidates if c.strategy_type == StrategyType.DYNAMIC_AVERAGING}
        context.exclude_symbols = da_symbols

        for evaluator in self._evaluators:
            if evaluator is da_evaluator:
                continue
            try:
                cands, skips = evaluator.identify_candidates(context)
                all_candidates.extend(cands)
                # Suppress DA skip records for symbols where this evaluator produced a candidate
                mle_symbols = {c.symbol for c in cands}
                for skip in skips:
                    if skip.symbol not in mle_symbols:
                        all_skipped.append(skip)
            except Exception:
                logger.error("Evaluator %s failed", evaluator.strategy_type.value, exc_info=True)

        # Deduplicate: same symbol can only have the highest-priority strategy type.
        # Multiple candidates from the same strategy (e.g. DA1 + DA2) are kept.
        symbol_map: dict[str, list[NormalizedCandidate]] = {}
        for c in all_candidates:
            symbol_map.setdefault(c.symbol, []).append(c)

        deduplicated: list[NormalizedCandidate] = []
        for sym, cands in symbol_map.items():
            cands.sort(key=lambda c: PRIORITY_ORDER.get(c.strategy_type, 99))
            best = cands[0]
            deduplicated.append(best)

            # Reject lower-priority *strategy types* only; same-strategy legs are kept
            for rejected in cands[1:]:
                if rejected.strategy_type == best.strategy_type:
                    deduplicated.append(rejected)
                    continue
                all_skipped.append(
                    SkippedCandidate(
                        symbol=sym,
                        exchange=rejected.exchange,
                        strategy_type=rejected.strategy_type,
                        cmp=rejected.cmp,
                        level_or_leg=rejected.level_or_leg,
                        reason_code=ReasonCode.DUPLICATE_ORDER,
                        reason_message="Higher-priority strategy selected for this symbol.",
                        suggested_action="Review the selected strategy.",
                        technical_details=f"Selected: {best.strategy_type.value}, rejected: {rejected.strategy_type.value}",
                    )
                )

        deduplicated.sort(key=lambda c: (PRIORITY_ORDER.get(c.strategy_type, 99), c.symbol))

        summary = CandidateSummary(
            total=len(deduplicated),
            ready=sum(1 for c in deduplicated if c.status == CandidateStatus.READY),
            warning=sum(1 for c in deduplicated if c.status == CandidateStatus.WARNING),
            review=sum(1 for c in deduplicated if c.status == CandidateStatus.REVIEW),
            skipped=len(all_skipped),
            capital_required=sum(c.amount for c in deduplicated if c.is_selectable),
        )

        return CandidateResult(
            strategy_type="UNIFIED",
            candidates=deduplicated,
            skipped=all_skipped,
            summary=summary,
        )

    @staticmethod
    def result_to_dict(result: CandidateResult) -> dict:
        """Convert result to JSON-serializable dict for storage/API response."""
        return {
            "strategy_type": result.strategy_type,
            "candidates": [asdict(c) for c in result.candidates],
            "skipped": [asdict(s) for s in result.skipped],
            "summary": asdict(result.summary),
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }
