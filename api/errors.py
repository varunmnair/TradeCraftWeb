"""Error handling helpers."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import Request, status
from fastapi.responses import JSONResponse


class ServiceError(Exception):
    def __init__(
        self,
        message: str,
        *,
        error_code: str = "bad_request",
        http_status: int = status.HTTP_400_BAD_REQUEST,
        context: Optional[Dict[str, Any]] = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.http_status = http_status
        self.context = context or {}
        self.retryable = retryable
        self.message = message

    def to_response(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "context": self.context,
            "retryable": self.retryable,
        }


def format_error_response(
    message: str,
    *,
    error_code: str = "internal_error",
    context: Optional[Dict[str, Any]] = None,
    retryable: bool = False,
) -> Dict[str, Any]:
    return {
        "error_code": error_code,
        "message": message,
        "context": context or {},
        "retryable": retryable,
    }


async def service_error_handler(request: Request, exc: ServiceError):
    return JSONResponse(status_code=exc.http_status, content=exc.to_response())


async def generic_error_handler(request: Request, exc: Exception):
    content = format_error_response(str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=content
    )
