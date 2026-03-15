"""Service wrapper for the AI analyst tools."""

from __future__ import annotations

from typing import Dict

from agent.manager import AgentManager
from core.runtime.session_registry import SessionRegistry


class AIService:
    def __init__(self, registry: SessionRegistry) -> None:
        self._registry = registry

    def ask(self, session_id: str, prompt: str) -> Dict[str, str]:
        context = self._registry.get_session(session_id)
        if not context:
            raise ValueError("Invalid or expired session_id")

        manager = AgentManager(context.broker)
        response = manager.ask(prompt)
        return {"response": response}
