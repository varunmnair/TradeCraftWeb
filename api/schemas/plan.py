from __future__ import annotations

from typing import Any, Dict, List, Literal

from pydantic import BaseModel

from api.schemas.common import JobQueuedResponse


class PlanGenerateRequest(BaseModel):
    session_id: str
    apply_risk: bool = False


class DynamicAvgGenerateRequest(BaseModel):
    session_id: str


class EntriesLatestResponse(BaseModel):
    strategy_type: Literal["multi_level", "dynamic_averaging"]
    plan: List[Dict[str, Any]]
    skipped: List[Dict[str, Any]]


PlanLatestResponse = EntriesLatestResponse

PlanGenerateResponse = JobQueuedResponse
