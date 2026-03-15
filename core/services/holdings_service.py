"""Holdings view layer for the API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.holdings import HoldingsAnalyzer
from core.runtime.session_registry import SessionRegistry
from core.utils import sanitize_for_json


class HoldingsService:
    def __init__(self, registry: SessionRegistry, analyzer_cls=HoldingsAnalyzer) -> None:
        self._registry = registry
        self._analyzer_cls = analyzer_cls

    def get_holdings_snapshot(self, session_id: str) -> List[Dict[str, Any]]:
        context = self._get_context(session_id)
        holdings = context.session_cache.get_holdings()
        return sanitize_for_json(holdings)

    def analyze_holdings(
        self,
        session_id: str,
        *,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = "ROI/Day",
    ) -> Dict[str, Any]:
        context = self._get_context(session_id)
        cmp_manager = context.session_cache.get_cmp_manager()
        analyzer = self._analyzer_cls(context.broker.user_id, context.broker_name)
        results = analyzer.analyze_holdings(context.broker, cmp_manager, filters=filters, sort_by=sort_by)
        return {"items": sanitize_for_json(results)}

    def _get_context(self, session_id: str):
        context = self._registry.get_session(session_id)
        if not context:
            raise ValueError("Invalid or expired session_id")
        return context
