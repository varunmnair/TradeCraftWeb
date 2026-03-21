"""Risk adjustment helpers for draft plans."""

from __future__ import annotations

from typing import Any, Dict, List

from core.multilevel_entry import MultiLevelEntryPlanner
from core.runtime.session_registry import SessionRegistry
from core.utils import sanitize_for_json


class RiskService:
    def __init__(self, registry: SessionRegistry) -> None:
        self._registry = registry

    def apply_risk(
        self, session_id: str, draft_plan: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        context = self._get_context(session_id)
        session_cache = context.session_cache
        strategy = MultiLevelEntryPlanner(
            context.broker,
            session_cache.get_cmp_manager(),
            session_cache.get_holdings(),
            session_cache.get_entry_levels(),
            session_cache.get_gtt_cache(),
        )
        adjusted = strategy.apply_risk_to_plan(draft_plan)
        return {
            "plan": sanitize_for_json(adjusted.get("plan", [])),
            "skipped": sanitize_for_json(adjusted.get("skipped", [])),
            "pending_cmp": sanitize_for_json(adjusted.get("pending_cmp", [])),
        }

    def _get_context(self, session_id: str):
        context = self._registry.get_session(session_id)
        if not context:
            raise ValueError("Invalid or expired session_id")
        return context
