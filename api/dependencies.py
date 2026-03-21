"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends, Request

from api import config
from api.errors import ServiceError
from core.auth.context import UserContext
from core.runtime.job_runner import JobRunner
from core.runtime.session_registry import SessionRegistry
from core.security.confirm_token_store import ConfirmTokenStore, get_confirm_store
from core.security.jwt import TokenError
from core.services.ai_service import AIService
from core.services.auth_service import AuthService
from core.services.broker_auth_service import BrokerAuthStateService
from core.services.broker_connection_service import BrokerConnectionService
from core.services.cmp_refresh_service import CMPRefreshService
from core.services.entry_plan_service import EntryPlanService
from core.services.gtt_service import GTTService
from core.services.holdings_service import HoldingsService
from core.services.ohlcv_refresh_service import OhlcvRefreshService
from core.services.risk_service import RiskService
from core.services.session_service import SessionService
from core.services.symbol_catalog_service import SymbolCatalogService
from core.services.trades_service import TradesService, get_trades_service
from core.session_manager import SessionManager
from db.database import SessionLocal, get_db

JOB_HOLDINGS_ANALYZE = "holdings_analyze"
JOB_PLAN_GENERATE = "plan_generate"
JOB_DYNAMIC_AVG_GENERATE = "dynamic_avg_generate"
JOB_RISK_APPLY = "risk_apply"
JOB_GTT_PREVIEW = "gtt_preview"
JOB_GTT_APPLY = "gtt_apply"
JOB_TRADES_SYNC = "trades_sync"
JOB_SYMBOL_CATALOG_IMPORT = "symbol_catalog_import"
JOB_CMP_REFRESH = "cmp_refresh"
JOB_OHLCV_REFRESH = "ohlcv_refresh"


_session_manager = SessionManager(dev_mode=config.IS_DEV)
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
_trades_service = get_trades_service()
_symbol_catalog_service = SymbolCatalogService()


def _sync_upstox_trades_job(payload: dict) -> dict:
    user_id = payload.get("user_id")
    connection_id = payload.get("connection_id")
    days = payload.get("days", 400)

    if not user_id or not connection_id:
        return {"error": "Missing user_id or connection_id"}

    broker_service = _broker_connection_service
    connection = broker_service.get_connection(connection_id)
    if not connection:
        return {"error": "Connection not found"}

    token_bundle = _session_manager.get_token_bundle(
        "upstox", connection_id=connection_id
    )
    if not token_bundle:
        return {"error": "Upstox not connected"}

    from brokers.upstox_broker import UpstoxBroker

    broker = UpstoxBroker(
        broker_user_id=connection.broker_user_id or "",
        api_key="",
        api_secret="",
        redirect_uri="",
    )
    broker.set_session_context(
        session_manager=_session_manager, connection_id=connection_id
    )

    try:
        result = _trades_service.sync_upstox_trades(user_id, broker, days)
        return result
    except Exception as e:
        return {"error": str(e)}


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
            "multi_level",
            apply_risk=payload.get("apply_risk", False),
        ),
    )
    _job_runner.register_handler(
        JOB_DYNAMIC_AVG_GENERATE,
        lambda payload: _entry_plan_service.generate_plan(
            payload["session_id"],
            "dynamic_averaging",
            apply_risk=False,
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
    _job_runner.register_handler(
        JOB_TRADES_SYNC,
        lambda payload: _sync_upstox_trades_job(payload),
    )
    _job_runner.register_handler(
        JOB_SYMBOL_CATALOG_IMPORT,
        lambda payload: _symbol_catalog_service.import_csv(
            csv_content=payload["csv_content"],
            replace=payload.get("replace", True),
        ),
    )
    _job_runner.register_handler(
        JOB_CMP_REFRESH,
        lambda payload: CMPRefreshService().refresh(
            session_manager=_session_manager,
            connection_id=payload["connection_id"],
        ),
    )
    _job_runner.register_handler(
        JOB_OHLCV_REFRESH,
        lambda payload: OhlcvRefreshService().refresh(
            session_manager=_session_manager,
            connection_id=payload["connection_id"],
            days=payload.get("days", 200),
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


def get_trades_service() -> TradesService:
    return _trades_service


def get_symbol_catalog_service() -> SymbolCatalogService:
    return _symbol_catalog_service


def get_db_session():
    yield from get_db()


def get_current_user(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> UserContext:
    from core.auth.active_connection_store import get_active_connection_store

    auth_header = request.headers.get("Authorization")
    if not auth_header:
        if config.IS_DEV:
            return auth_service.ensure_dev_user()
        raise ServiceError(
            "Missing Authorization header", error_code="unauthorized", http_status=401
        )

    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise ServiceError(
            "Invalid authorization header", error_code="unauthorized", http_status=401
        )
    try:
        user_context = auth_service.decode_token(token)
        active_store = get_active_connection_store()
        active_connection_id = active_store.get_active_connection(user_context.user_id)
        user_context.active_broker_connection_id = active_connection_id
        return user_context
    except TokenError as exc:
        raise ServiceError(
            "Invalid access token", error_code="unauthorized", http_status=401
        ) from exc


def require_admin(user: UserContext = Depends(get_current_user)) -> UserContext:
    if not user.is_admin():
        raise ServiceError(
            "Admin privileges required", error_code="forbidden", http_status=403
        )
    return user


def require_trading_enabled(user: UserContext) -> None:
    """Require that trading is enabled for the user."""
    if not user.trading_enabled:
        raise ServiceError(
            "Read-only mode. Trading is disabled. Contact admin to enable trading.",
            error_code="trading_disabled",
            http_status=403,
        )
