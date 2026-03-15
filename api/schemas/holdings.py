from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from api.schemas.common import JobQueuedResponse


class HoldingsAnalyzeRequest(BaseModel):
    session_id: str
    filters: Optional[Dict[str, Any]] = None
    sort_by: str = "ROI/Day"


class HoldingsLatestResponse(BaseModel):
    items: List[Dict[str, Any]]


HoldingsAnalyzeResponse = JobQueuedResponse
