from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from api.schemas.common import JobQueuedResponse


class GTTPreviewRequest(BaseModel):
    session_id: str
    plan: List[Dict[str, Any]]


class GTTApplyRequest(GTTPreviewRequest):
    confirmation_token: str = Field(..., min_length=4)


class GTTOrdersResponse(BaseModel):
    orders: List[Dict[str, Any]]


class GTTResultResponse(BaseModel):
    results: List[Dict[str, Any]]


GTTPreviewResponse = JobQueuedResponse
GTTApplyResponse = JobQueuedResponse


class GTTConfirmRequest(BaseModel):
    session_id: str
    plan: List[Dict[str, Any]]


class GTTConfirmResponse(BaseModel):
    token: str
    expires_at: str


class GTTDeleteRequest(BaseModel):
    session_id: str
    order_ids: List[str] = Field(..., min_length=1)


class GTTDeleteResponse(BaseModel):
    deleted: List[str]
    count: int


class GTTAdjustRequest(BaseModel):
    session_id: str
    order_ids: List[str] = Field(..., min_length=1)
    target_variance: float = Field(..., ge=-50, le=50)


class GTTAdjustResponse(BaseModel):
    adjusted: List[Dict[str, Any]]
    failed: List[Dict[str, Any]]
    count: int
