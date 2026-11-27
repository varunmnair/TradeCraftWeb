"""UI configuration endpoints (global, admin-managed)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from api.dependencies import get_current_user, get_ui_configuration_service, require_admin
from api.errors import ServiceError
from core.audit import log_audit
from core.auth.context import UserContext
from core.services.ui_configuration_service import UiConfigurationService

router = APIRouter(tags=["ui-config"])


class UiColumnOverride(BaseModel):
    id: str
    visible: bool | None = None
    sortable: bool | None = None
    filterable: bool | None = None
    position: int | None = None


class UiSortConfig(BaseModel):
    field: str
    direction: Literal["asc", "desc"]


class UiPageConfigUpdate(BaseModel):
    pageId: str | None = None
    searchEnabled: bool | None = None
    searchField: str | None = None
    defaultPageSize: int | None = None
    allowedPageSizes: list[int] | None = None
    density: Literal["compact", "comfortable"] | None = None
    selectionEnabled: bool | None = None
    defaultSort: UiSortConfig | None = None
    mobilePrimaryFields: list[str] | None = None
    mobileDetailFields: list[str] | None = None
    columns: list[UiColumnOverride] | None = None


def _config_response(config: dict[str, Any]) -> dict[str, Any]:
    return config


@router.get("/admin/ui-config/pages")
def list_ui_config_pages(
    _user: UserContext = Depends(require_admin),
    service: UiConfigurationService = Depends(get_ui_configuration_service),
) -> dict[str, Any]:
    return {"pages": service.list_pages()}


@router.get("/ui-config/{page_id}")
def get_ui_config(
    page_id: str,
    _user: UserContext = Depends(get_current_user),
    service: UiConfigurationService = Depends(get_ui_configuration_service),
) -> dict[str, Any]:
    try:
        return _config_response(service.get_effective_config(page_id))
    except KeyError as exc:
        raise ServiceError(
            f"Unknown UI config page: {page_id}",
            error_code="not_found",
            http_status=404,
            context={"page_id": page_id},
        ) from exc
    except Exception as exc:
        raise ServiceError(
            "Failed to load UI configuration",
            error_code="ui_config_read_failed",
            http_status=500,
            context={"page_id": page_id},
        ) from exc


@router.put("/admin/ui-config/{page_id}")
def update_ui_config(
    page_id: str,
    payload: UiPageConfigUpdate,
    request: Request,
    user: UserContext = Depends(require_admin),
    service: UiConfigurationService = Depends(get_ui_configuration_service),
) -> dict[str, Any]:
    request_id = getattr(request.state, "request_id", None)
    try:
        config = payload.model_dump(exclude_none=True)
        saved = service.save_config(page_id, config, user_id=user.user_id)
        log_audit(
            action="ui_config.update",
            user=user,
            resource_type="ui_config",
            resource_id=page_id,
            metadata={"page_id": page_id, "operation": "UPDATE"},
            request_id=request_id,
        )
        return _config_response(saved)
    except KeyError as exc:
        log_audit(
            action="ui_config.update_failed",
            user=user,
            resource_type="ui_config",
            resource_id=page_id,
            metadata={"page_id": page_id, "operation": "UPDATE", "error": f"Unknown page: {page_id}"},
            request_id=request_id,
        )
        raise ServiceError(
            f"Unknown UI config page: {page_id}",
            error_code="not_found",
            http_status=404,
            context={"page_id": page_id},
        ) from exc
    except ValueError as exc:
        log_audit(
            action="ui_config.update_failed",
            user=user,
            resource_type="ui_config",
            resource_id=page_id,
            metadata={"page_id": page_id, "operation": "UPDATE", "error": str(exc)},
            request_id=request_id,
        )
        raise ServiceError(
            str(exc),
            error_code="invalid_ui_config",
            http_status=400,
            context={"page_id": page_id},
        ) from exc
    except Exception as exc:
        log_audit(
            action="ui_config.update_failed",
            user=user,
            resource_type="ui_config",
            resource_id=page_id,
            metadata={"page_id": page_id, "operation": "UPDATE", "error": str(exc)},
            request_id=request_id,
        )
        raise ServiceError(
            "Failed to save UI configuration",
            error_code="ui_config_write_failed",
            http_status=500,
            context={"page_id": page_id},
        ) from exc


@router.post("/admin/ui-config/{page_id}/reset")
def reset_ui_config(
    page_id: str,
    request: Request,
    user: UserContext = Depends(require_admin),
    service: UiConfigurationService = Depends(get_ui_configuration_service),
) -> dict[str, Any]:
    request_id = getattr(request.state, "request_id", None)
    try:
        config = service.reset_config(page_id, user_id=user.user_id)
        log_audit(
            action="ui_config.reset",
            user=user,
            resource_type="ui_config",
            resource_id=page_id,
            metadata={"page_id": page_id, "operation": "RESET"},
            request_id=request_id,
        )
        return _config_response(config)
    except KeyError as exc:
        log_audit(
            action="ui_config.reset_failed",
            user=user,
            resource_type="ui_config",
            resource_id=page_id,
            metadata={"page_id": page_id, "operation": "RESET", "error": f"Unknown page: {page_id}"},
            request_id=request_id,
        )
        raise ServiceError(
            f"Unknown UI config page: {page_id}",
            error_code="not_found",
            http_status=404,
            context={"page_id": page_id},
        ) from exc
    except Exception as exc:
        log_audit(
            action="ui_config.reset_failed",
            user=user,
            resource_type="ui_config",
            resource_id=page_id,
            metadata={"page_id": page_id, "operation": "RESET", "error": str(exc)},
            request_id=request_id,
        )
        raise ServiceError(
            "Failed to reset UI configuration",
            error_code="ui_config_reset_failed",
            http_status=500,
            context={"page_id": page_id},
        ) from exc