"""Shared FastAPI dependencies."""

from __future__ import annotations

import os
from typing import Any, Dict

from fastapi import Depends, Request

from api.errors import ServiceError
from core.auth.context import UserContext
from core.runtime.job_runner import JobRunner
from core.runtime.session_registry import SessionRegistry
from core.security.oauth_state import OAuthStateStore, get_oauth_state_store
from core.session_manager import SessionManager
from core.security.confirm_token_store import ConfirmTokenStore, get_confirm_store
from core.security.jwt import TokenError
from core.services.ai_service import AIService
from core.services.auth_service import AuthService
from core.services.broker_auth_service import BrokerAuthStateService
from core.services.broker_connection_service import BrokerConnectionService
from core.services.entry_plan_service import EntryPlanService
from core.services.gtt_service import GTTService
from core.services.holdings_service import HoldingsService
from core.services.risk_service import RiskService
from core.services.session_service import SessionService
from db.database import SessionLocal, get_db


DEV_MODE = os.getenv("DEV_MODE", "1") in ("1", "true")

JOB_HOLDINGS_ANALYZE = "holdings_analyze"
JOB_PLAN_GENERATE = "plan_generate"
JOB_DYNAMIC_AVG_GENERATE = "dynamic_avg_generate"
JOB_RISK_APPLY = "risk_apply"
JOB_GTT_PREVIEW = "gtt_preview"
JOB_GTT_APPLY = "gtt_apply"


_session_manager = SessionManager(dev_mode=DEV_MODE)
_session_registry = SessionRegistry(session_manager=_session_manager)
_session_service = SessionService(registry=_session_registry)
_holdings_service = HoldingsService(_session_registry)
_entry_plan_service = EntryPlanService(_session_registry)
_risk_service = RiskService(_session_registry)
_gtt_service = GTTService(_session_registry)
_ai_service = AIService(_session_registry)
_broker_connection_service = BrokerConnectionService()
_broker_auth_state_service = BrokerAuthStateService()
_auth_service = AuthService()
_confirm_store = get_confirm_store()
_job_runner = JobRunner(SessionLocal, session_registry=_session_registry)


def _register_jobs() -> None:
    _job_runner.register_handler(
        JOB_HOLDINGS_ANALYZE,
        lambda payload: _holdings_service.analyze_holdings(
            payload["session_id"],
            filters=payload.get("filters"),
            sort_by=payload.get("sort_by", "ROI/Day"),
        ),
    )
    _job_runner.register_handler(
        JOB_PLAN_GENERATE,
        lambda payload: _entry_plan_service.generate_plan(
            payload["session_id"],
            apply_risk=payload.get("apply_risk", False),
        ),
    )
    _job_runner.register_handler(
        JOB_DYNAMIC_AVG_GENERATE,
        lambda payload: _entry_plan_service.generate_dynamic_avg(
            payload["session_id"],
        ),
    )
    _job_runner.register_handler(
        JOB_RISK_APPLY,
        lambda payload: _risk_service.apply_risk(
            payload["session_id"],
            payload.get("plan", []),
        ),
    )
    _job_runner.register_handler(
        JOB_GTT_PREVIEW,
        lambda payload: _gtt_service.place_orders(
            payload["session_id"],
            payload.get("plan", []),
            dry_run=True,
        ),
    )
    _job_runner.register_handler(
        JOB_GTT_APPLY,
        lambda payload: _gtt_service.place_orders(
            payload["session_id"],
            payload.get("plan", []),
            dry_run=False,
        ),
    )


_register_jobs()


def get_session_registry() -> SessionRegistry:
    return _session_registry


def get_session_service() -> SessionService:
    return _session_service


def get_session_manager() -> SessionManager:
    return _session_manager


def get_holdings_service() -> HoldingsService:
    return _holdings_service


def get_entry_plan_service() -> EntryPlanService:
    return _entry_plan_service


def get_risk_service() -> RiskService:
    return _risk_service


def get_gtt_service() -> GTTService:
    return _gtt_service


def get_ai_service() -> AIService:
    return _ai_service


def get_job_runner() -> JobRunner:
    return _job_runner


def get_broker_connection_service() -> BrokerConnectionService:
    return _broker_connection_service


def get_broker_auth_state_service() -> BrokerAuthStateService:
    return _broker_auth_state_service


def get_auth_service() -> AuthService:
    return _auth_service


def get_confirm_token_service() -> ConfirmTokenStore:
    return _confirm_store


def get_db_session():
    yield from get_db()


def get_current_user(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> UserContext:
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        if DEV_MODE:
            return auth_service.ensure_dev_user()
        raise ServiceError("Missing Authorization header", error_code="unauthorized", http_status=401)

    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise ServiceError("Invalid authorization header", error_code="unauthorized", http_status=401)
    try:
        return auth_service.decode_token(token)
    except TokenError as exc:
        raise ServiceError("Invalid access token", error_code="unauthorized", http_status=401) from exc


def require_admin(user: UserContext) -> None:
    if not user.is_admin():
        raise ServiceError("Admin privileges required", error_code="forbidden", http_status=403)
