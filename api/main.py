from __future__ import annotations

import logging
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from api.errors import ServiceError, generic_error_handler, service_error_handler
from api.routes import auth as auth_routes
from api.routes import broker_connections as broker_connection_routes
from api.routes import brokers as brokers_routes
from api.routes import holdings as holdings_routes
from api.routes import plan as plan_routes
from api.routes import risk as risk_routes
from api.routes import gtt as gtt_routes
from api.routes import jobs as jobs_routes
from api.routes import session as session_routes
from api.routes import ai as ai_routes
from api.routes import entry_strategy as entry_strategy_routes
from db.database import SessionLocal


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
LOGGER = logging.getLogger("tradecraftx.api")
HOSTED_MODE = os.getenv("HOSTED_MODE", "0") == "1"
DEV_MODE = os.getenv("DEV_MODE", "0") == "1"

# Path to UI build output
UI_DIST_PATH = Path(__file__).parent.parent / "ui" / "dist"


def create_app() -> FastAPI:
    app = FastAPI(title="TradeCraftX API", version="0.2.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):  # type: ignore[override]
        LOGGER.info("%s %s", request.method, request.url.path)
        response = await call_next(request)
        LOGGER.info("%s %s -> %s", request.method, request.url.path, response.status_code)
        return response

    app.add_exception_handler(ServiceError, service_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, generic_error_handler)  # type: ignore[arg-type]

    app.include_router(auth_routes.router)
    app.include_router(broker_connection_routes.router)
    app.include_router(brokers_routes.router)
    app.include_router(brokers_routes.zerodha_router)
    app.include_router(session_routes.router)
    app.include_router(holdings_routes.router)
    app.include_router(plan_routes.router)
    app.include_router(plan_routes.dynamic_avg_router)
    app.include_router(risk_routes.router)
    app.include_router(gtt_routes.router)
    app.include_router(jobs_routes.router)
    app.include_router(ai_routes.router)
    app.include_router(entry_strategy_routes.router)

    @app.get("/health")
    def health_check():
        return {"status": "ok"}

    @app.get("/ready")
    def readiness_check():
        try:
            with SessionLocal() as session:
                session.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=503, detail="database_unavailable") from exc

        if HOSTED_MODE and not os.getenv("TOKEN_ENCRYPTION_KEY"):
            raise HTTPException(status_code=503, detail="token_encryption_key_missing")
        return {"status": "ready"}

    # Serve static UI files if build exists and not in dev mode
    if DEV_MODE:
        LOGGER.info("DEV_MODE enabled - skipping UI static file serving")
    elif UI_DIST_PATH.exists():
        # Mount static files directory if it exists
        static_path = UI_DIST_PATH / "static"
        if static_path.exists():
            app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
        
        @app.get("/")
        async def serve_index():
            return FileResponse(str(UI_DIST_PATH / "index.html"))
        
        @app.get("/{path:path}")
        async def serve_spa(path: str):
            # Check if file exists in dist folder
            file_path = UI_DIST_PATH / path
            if file_path.exists() and file_path.is_file():
                return FileResponse(str(file_path))
            
            # Fallback to index.html for SPA routes
            return FileResponse(str(UI_DIST_PATH / "index.html"))
        
        LOGGER.info(f"Serving UI from {UI_DIST_PATH}")
    else:
        LOGGER.warning(f"UI build not found at {UI_DIST_PATH}. API-only mode.")

    return app


app = create_app()
