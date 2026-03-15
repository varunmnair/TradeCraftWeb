from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel

from api.schemas.common import JobQueuedResponse


class RiskApplyRequest(BaseModel):
    session_id: str
    plan: List[Dict[str, Any]]


class RiskApplyResponse(JobQueuedResponse):
    pass
