"""Audit logging utilities."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from core.auth.context import UserContext
from db.database import SessionLocal
from db.models import AuditEvent


logger = logging.getLogger(__name__)


def sanitize_for_audit(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove sensitive data from audit records."""
    if not data:
        return {}
    
    sensitive_keys = {
        "password", "token", "access_token", "refresh_token",
        "api_secret", "secret", "authorization", "jwt",
        "tokens", "encrypted_tokens", "broker_user_id",
    }
    
    result = {}
    for key, value in data.items():
        if key.lower() in sensitive_keys:
            result[key] = "[REDACTED]"
        elif isinstance(value, dict):
            result[key] = sanitize_for_audit(value)
        elif isinstance(value, list):
            result[key] = [
                sanitize_for_audit(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    
    return result


def log_audit(
    action: str,
    user: UserContext,
    resource_type: str,
    resource_id: Optional[str] = None,
    broker_connection_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    request_id: Optional[str] = None,
) -> None:
    """Log an audit event to the database.
    
    Args:
        action: The action being performed (e.g., 'login', 'order_place', 'upload_csv')
        user: The user context
        resource_type: Type of resource (e.g., 'session', 'entry_strategy', 'order')
        resource_id: ID of the resource (optional)
        broker_connection_id: Associated broker connection (optional)
        metadata: Additional metadata (will be sanitized)
        ip_address: Client IP address
        user_agent: Client user agent
        request_id: Request tracking ID
    """
    if not user.tenant_id or not user.user_id:
        logger.warning(f"Audit event skipped - no user context: {action}")
        return
    
    sanitized_metadata = sanitize_for_audit(metadata or {})
    
    try:
        db = SessionLocal()
        try:
            event = AuditEvent(
                tenant_id=user.tenant_id,
                user_id=user.user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                broker_connection_id=broker_connection_id,
                metadata_json=json.dumps(sanitized_metadata) if sanitized_metadata else None,
                ip_address=ip_address,
                user_agent=user_agent[:500] if user_agent else None,
                request_id=request_id,
            )
            db.add(event)
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to log audit event: {action} - {e}")


def require_trading_enabled(user: UserContext) -> None:
    """Check if trading is enabled for the user.
    
    Raises:
        PermissionError: If trading is not enabled
    """
    if not user.trading_enabled:
        raise PermissionError(
            "Trading is disabled. Contact admin to enable trading."
        )
