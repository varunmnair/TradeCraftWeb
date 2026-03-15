from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    context: Dict[str, Any] = {}
    retryable: bool = False


class JobQueuedResponse(BaseModel):
    job_id: int


class JobStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: Optional[int] = None
    user_id: Optional[int] = None
    session_id: str
    job_type: str
    status: str
    progress: float
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class JobStatusResponse(BaseModel):
    job: JobStatus


class JobListResponse(BaseModel):
    jobs: List[JobStatus]
