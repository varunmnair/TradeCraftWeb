"""Placement context validation and durable request idempotency.

This module is intentionally broker-agnostic. It does not decide prices,
tranches, triggers, or strategy eligibility; it only makes sure that a
placement request is tied to the correct user/device/broker context and that
the same request cannot reach the broker twice.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any, Callable, Dict, Optional

from sqlalchemy.exc import IntegrityError

from db import models

logger = logging.getLogger("tradecraftx.placement")

COMPLETED_STATUSES = {"completed", "queued"}
UNCERTAIN_PATTERNS = (
    r"\btimed?\s*out\b",
    r"timeout",
    r"connection (?:was )?(?:reset|closed|lost|refused)",
    r"socket",
    r"gateway",
    r"temporarily unavailable",
    r"service unavailable",
    r"internal server error",
    r"\b5\d\d\b",
    r"unknown (?:order|response|status|result)",
    r"could not (?:verify|confirm|determine)",
    r"unable to (?:verify|confirm|determine)",
    r"uncertain",
)


class PlacementContextError(Exception):
    """The session/broker context for a placement could not be validated."""

    def __init__(
        self, message: str, http_status: int = 403, reason: Optional[str] = None
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.reason = reason or "invalid_context"


def _session_reason(message: str) -> str:
    lowered = message.lower()
    if "another user" in lowered:
        return "session_wrong_user"
    if "another device" in lowered:
        return "session_wrong_device"
    return "session_missing"


def placement_error_code(exc: PlacementContextError) -> str:
    """Return a machine-readable API error code for a context failure."""
    if exc.reason.startswith("session_") or exc.reason.endswith("_mismatch"):
        return "session_restoration_required"
    return "invalid_placement_context"


class PlacementConflictError(Exception):
    """An idempotency key is already in use by another request."""

    def __init__(self, message: str, http_status: int = 409) -> None:
        super().__init__(message)
        self.http_status = http_status


def request_fingerprint(payload: Any) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def resolve_idempotency_key(
    *,
    user_id: int,
    session_id: str,
    device_id: Optional[str],
    payload: Any,
    explicit_key: Optional[str] = None,
) -> tuple[str, str]:
    """Return the key to claim and the hash that identifies this exact request."""
    fingerprint = request_fingerprint(payload)
    if explicit_key and explicit_key.strip():
        return explicit_key.strip()[:255], fingerprint
    # Fallback for clients that cannot send an explicit key (older UI builds and
    # internal callers). It is stable for the same logical request.
    fallback = request_fingerprint(
        {
            "user_id": user_id,
            "session_id": session_id,
            "device_id": device_id,
            "request": fingerprint,
        }
    )
    return f"auto-{fallback[:40]}", fingerprint


def validate_placement_context(
    *,
    registry: Any,
    session_id: str,
    user: Any,
    expected_connection_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Resolve and validate the broker context before any broker call.

    Raises:
        PlacementContextError: session ownership/device/broker context is wrong.
    """
    try:
        context = registry.require_access(session_id, user)
    except ValueError as exc:
        raise PlacementContextError(str(exc), 403, _session_reason(str(exc))) from exc

    connection_id = context.trading_broker_connection_id
    if connection_id is None:
        raise PlacementContextError(
            "This trading session is not bound to a broker connection. "
            "Reconnect the broker and start a new session.",
            409,
            "session_unbound",
        )

    active_connection_id = getattr(user, "active_broker_connection_id", None)
    if expected_connection_id is not None and expected_connection_id != connection_id:
        raise PlacementContextError(
            "Requested broker connection does not match this trading session.",
            403,
            "broker_connection_mismatch",
        )
    if active_connection_id is not None and active_connection_id != connection_id:
        raise PlacementContextError(
            "Broker selected on this device does not match this trading session. "
            "Reconnect the broker and start a new session.",
            403,
            "active_connection_mismatch",
        )

    return {
        "session_id": session_id,
        "user_id": user.user_id,
        "broker_name": context.broker_name,
        "broker_user_id": context.broker_user_id,
        "broker_connection_id": connection_id,
        "device_id": getattr(user, "device_id", None),
    }


def classify_broker_error(exc: BaseException) -> str:
    """Classify a broker failure as a definitive Fail or an Uncertain response."""
    message = f"{type(exc).__name__} {exc}"
    if any(re.search(pattern, message, re.IGNORECASE) for pattern in UNCERTAIN_PATTERNS):
        return "Uncertain"
    return "Fail"


class PlacementGuardService:
    """Persist and replay placement outcomes using a unique request key."""

    def __init__(self, session_factory: Callable[[], Any]) -> None:
        self._session_factory = session_factory

    def claim(
        self,
        *,
        user_id: int,
        idempotency_key: str,
        request_hash_value: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        with self._session_factory() as db:
            try:
                record = models.OrderPlacement(
                    user_id=user_id,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash_value,
                    session_id=context["session_id"],
                    broker_name=context.get("broker_name"),
                    broker_connection_id=context.get("broker_connection_id"),
                    device_id=context.get("device_id"),
                    status="in_flight",
                )
                db.add(record)
                db.commit()
                db.refresh(record)
                return {"claimed": True, "record": self._serialize(record)}
            except IntegrityError:
                db.rollback()
                existing = (
                    db.query(models.OrderPlacement)
                    .filter(
                        models.OrderPlacement.user_id == user_id,
                        models.OrderPlacement.idempotency_key == idempotency_key,
                    )
                    .one_or_none()
                )
                if existing is None:  # pragma: no cover - defensive for exotic drivers
                    raise PlacementConflictError("Unable to reserve placement request")
                if existing.request_hash != request_hash_value:
                    raise PlacementConflictError(
                        "Idempotency key was already used for a different order request."
                    )
                if existing.status in COMPLETED_STATUSES:
                    return {
                        "claimed": False,
                        "replayed": True,
                        "record": self._serialize(existing),
                    }
                if existing.status == "uncertain":
                    raise PlacementConflictError(
                        "The previous placement has an uncertain broker response. "
                        "Verify it in the broker app before trying again."
                    )
                if existing.status == "failed":
                    # A definitive failure never reached the broker, so the same
                    # request can safely be retried under the original key.
                    existing.status = "in_flight"
                    existing.error_json = None
                    existing.result_json = None
                    db.commit()
                    return {"claimed": True, "record": self._serialize(existing)}
                raise PlacementConflictError(
                    "A matching placement is already being processed. "
                    "Wait for it to finish before retrying."
                )

    def complete(
        self,
        *,
        user_id: int,
        idempotency_key: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        with self._session_factory() as db:
            record = (
                db.query(models.OrderPlacement)
                .filter(
                    models.OrderPlacement.user_id == user_id,
                    models.OrderPlacement.idempotency_key == idempotency_key,
                )
                .one_or_none()
            )
            if record is None:
                logger.warning(
                    "No placement record for user=%s key=%s", user_id, idempotency_key
                )
                return
            record.status = status
            record.result_json = json.dumps(result or {}, default=str)
            record.error_json = json.dumps({"message": error}) if error else None
            db.commit()

    def execute(
        self,
        *,
        user_id: int,
        idempotency_key: str,
        request_hash_value: str,
        context: Dict[str, Any],
        operation: Callable[[], Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Claim a request, run it once, and persist the per-order outcome."""
        claim = self.claim(
            user_id=user_id,
            idempotency_key=idempotency_key,
            request_hash_value=request_hash_value,
            context=context,
        )
        if not claim["claimed"]:
            replayed = claim["record"]
            return {
                "results": (json.loads(replayed.get("result_json") or "{}")).get(
                    "results", []
                ),
                "replayed": True,
                "placement_status": replayed.get("status"),
            }

        try:
            result = operation()
        except Exception as exc:
            self.complete(
                user_id=user_id,
                idempotency_key=idempotency_key,
                status="failed",
                error=str(exc),
            )
            raise

        statuses = [str(r.get("status", "")).lower() for r in result.get("results", [])]
        if "uncertain" in statuses:
            status = "uncertain"
        elif any(s in {"fail", "failed"} for s in statuses):
            status = "failed"
        else:
            status = "completed"
        self.complete(
            user_id=user_id,
            idempotency_key=idempotency_key,
            status=status,
            result=result,
        )
        return result

    @staticmethod
    def _serialize(record: Any) -> Dict[str, Any]:
        return {
            "id": record.id,
            "user_id": record.user_id,
            "idempotency_key": record.idempotency_key,
            "request_hash": record.request_hash,
            "session_id": record.session_id,
            "broker_name": record.broker_name,
            "broker_connection_id": record.broker_connection_id,
            "device_id": record.device_id,
            "status": record.status,
            "result_json": record.result_json,
            "error_json": record.error_json,
        }
