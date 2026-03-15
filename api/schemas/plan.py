from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel

from api.schemas.common import JobQueuedResponse


class PlanGenerateRequest(BaseModel):
    session_id: str
    apply_risk: bool = False


class PlanLatestResponse(BaseModel):
    plan: List[Dict[str, Any]]
    skipped: List[Dict[str, Any]]


class DynamicAvgGenerateRequest(BaseModel):
    session_id: str


PlanGenerateResponse = JobQueuedResponse
