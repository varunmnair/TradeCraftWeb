from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.dependencies import get_ai_service, get_current_user, get_session_registry
from api.errors import ServiceError
from core.auth.context import UserContext
from core.runtime.session_registry import SessionRegistry
from core.services.ai_service import AIService

router = APIRouter(prefix="/ai", tags=["ai"])


class AIChatRequest(BaseModel):
    session_id: str
    message: str
    context: Optional[Dict[str, Any]] = None


class AIAction(BaseModel):
    type: str = Field(..., description="Action type: filter, sort, analyze")
    params: Dict[str, Any] = Field(
        default_factory=dict, description="Action parameters"
    )


class AIChatResponse(BaseModel):
    response: str
    actions: Optional[List[AIAction]] = None


@router.post("/chat", response_model=AIChatResponse)
def chat_with_ai(
    payload: AIChatRequest,
    ai_service: AIService = Depends(get_ai_service),
    registry: SessionRegistry = Depends(get_session_registry),
    current_user: UserContext = Depends(get_current_user),
):
    registry.require_access(payload.session_id, current_user)
    try:
        # Build context string from payload context
        context_str = ""
        if payload.context:
            page = payload.context.get("page", "unknown")
            selected = payload.context.get("selected_symbols", [])
            context_str = f"\n\nCurrent page: {page}"
            if selected:
                context_str += f"\nSelected symbols: {', '.join(selected)}"

        # Combine user message with context
        full_prompt = payload.message + context_str

        result = ai_service.ask(payload.session_id, full_prompt)
        return AIChatResponse(
            response=result.get("response", ""),
            actions=None,  # TODO: Parse actionable suggestions from AI response
        )
    except Exception as exc:
        raise ServiceError(str(exc), error_code="ai_error", http_status=500) from exc
