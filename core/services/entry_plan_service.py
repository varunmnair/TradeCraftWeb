"""Entry planning orchestration service."""

from __future__ import annotations

from typing import Any, Dict

from core.multilevel_entry import MultiLevelEntryStrategy
from core.dynamic_avg import DynamicAveragingPlanner
from core.runtime.session_registry import SessionRegistry
from core.utils import sanitize_for_json


class EntryPlanService:
    def __init__(self, registry: SessionRegistry) -> None:
        self._registry = registry

    def list_entry_levels(self, session_id: str) -> Dict[str, Any]:
        context = self._get_context(session_id)
        entry_levels = context.session_cache.get_entry_levels()
        return {"items": sanitize_for_json(entry_levels)}

    def generate_plan(self, session_id: str, *, apply_risk: bool = False) -> Dict[str, Any]:
        context = self._get_context(session_id)
        session_cache = context.session_cache
        cmp_manager = session_cache.get_cmp_manager()
        holdings = session_cache.get_holdings()
        entry_levels = session_cache.get_entry_levels()
        gtt_cache = session_cache.get_gtt_cache()

        strategy = MultiLevelEntryStrategy(
            context.broker,
            cmp_manager,
            holdings,
            entry_levels,
            gtt_cache,
        )
        candidates = strategy.identify_candidates()
        plan = strategy.generate_plan(candidates, apply_risk_management=apply_risk)
        return {
            "plan": sanitize_for_json(plan),
            "skipped": sanitize_for_json(strategy.skipped_orders),
        }

    def generate_dynamic_avg(self, session_id: str) -> Dict[str, Any]:
        context = self._get_context(session_id)
        session_cache = context.session_cache
        cmp_manager = session_cache.get_cmp_manager()
        holdings = session_cache.get_holdings()
        entry_levels = session_cache.get_entry_levels()
        gtt_cache = session_cache.get_gtt_cache()

        planner = DynamicAveragingPlanner(
            broker=context.broker,
            cmp_manager=cmp_manager,
            holdings=holdings,
            entry_levels=entry_levels,
            gtt_cache=gtt_cache,
            trigger_offset_factor=0.3,
        )
        candidates = planner.identify_candidates()
        plan = planner.generate_buy_plan(candidates)
        return {
            "plan": sanitize_for_json(plan),
            "skipped": sanitize_for_json(planner.skipped_symbols),
        }

    def _get_context(self, session_id: str):
        context = self._registry.get_session(session_id)
        if not context:
            raise ValueError("Invalid or expired session_id")
        return context
