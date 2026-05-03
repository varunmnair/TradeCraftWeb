# AGENTS.md

## Purpose
- TradeCraftX is an API-first trading automation and analysis application for Zerodha and Upstox.
- Web UI (React/Vite) is the primary interface; CLI exists for legacy/debugging only.
- This document provides autonomous agents the minimum context they need to work safely.

## Repository Layout
- `api/`: FastAPI backend (auth, sessions, jobs, trading workflows). Entry point: `api/main.py`.
- `ui/`: React + TypeScript + MUI, built with Vite. API calls go directly to `:8000` via `ui/.env` (`VITE_API_BASE_URL=http://localhost:8000`).
- `core/`: Trading engines — CLI, risk, CMP cache, session cache, holdings analytics, entry planners, services.
- `brokers/`: Broker adapters (`ZerodhaBroker`, `UpstoxBroker`) plus `BrokerFactory`.
- `agent/`: AI-facing helpers (LLM provider, strategy agent loop, tool registry).
- `db/`: SQLAlchemy models, Alembic migrations, database config.
- `data/`: OHLCV cache, tradebook CSVs, runtime artifacts. Gitignored.
- `auth/`: OAuth state tokens (temporary). Broker tokens stored encrypted in DB. Treat as sensitive.

## Environment & Setup
- **Python**: 3.10+ with venv: `python -m venv venv && venv\Scripts\activate` (Windows).
- **Node.js**: v18+ for frontend.
- **Backend deps**: `pip install -r requirements.txt`
- **Frontend deps**: `cd ui && npm install`
- **Frontend env**: Copy `ui/.env.example` to `ui/.env` (sets `VITE_API_BASE_URL=http://localhost:8000`)
- **Env files**: Copy `.env.example` to `.env`. Use `APP_MODE=dev` (or `prod`). `DEV_MODE`/`HOSTED_MODE` are deprecated.
- **DB init**: `python -m alembic upgrade head` (SQLite at `data/tradecraftx.db` by default).
- **Dev mode auto-provisioning**: With `APP_MODE=dev`, `POST /auth/login` auto-creates a dev tenant/user.

## Primary Commands

### Backend
```bash
python -m uvicorn api.main:app --reload --port 8000   # Dev API server
python menu_cli.py                                      # Legacy CLI menu
```

### Frontend
```bash
cd ui
npm run dev      # Dev server at localhost:5173 (proxies API to :8000)
npm run build    # tsc -b && vite build (outputs to ui/dist/)
npm run lint     # ESLint
npm run preview  # Preview production build
```

### Docker
```bash
docker compose up   # Runs backend with APP_MODE=prod, auto-migrates DB
```

### Lint & Test
```bash
python -m ruff check api core brokers       # Ruff lint (primary linter per pyproject.toml)
python -m ruff format --check api core      # Format check
python -m pylint api core brokers            # Pylint (secondary)
cd ui && npm run lint                        # ESLint

python -m pytest tests/                      # All tests
python -m pytest tests/ -k keyword           # Filter by keyword
python -m pytest tests/test_file.py::TestCls::test_method  # Single test
```

## Architecture Highlights
- **API-first**: FastAPI app created in `api/main.py:create_app()` with `app = create_app()` at module level.
- **Route modules**: `api/routes/` — auth, admin, brokers, broker_connections, session, holdings, holdings_v2, plan, risk, gtt, jobs, ai, entry_strategy, market.
- **Dependency injection**: `api/dependencies.py` — singletons for all services, `get_current_user`, `require_admin`, `require_trading_enabled`.
- **Session management**: `SessionRegistry` + `SessionManager` + `SessionService`. Trading sessions are broker-scoped via `connection_id`.
- **Active broker connection**: Use `_require_active_connection_scope()` for broker-scoped data. Active connection stored in `ActiveConnectionStore`.
- **Job-based async**: Long-running tasks use `JobRunner` pattern. Job types defined in `api/dependencies.py` (e.g., `JOB_HOLDINGS_ANALYZE`, `JOB_GTT_APPLY`, `JOB_TRADES_SYNC`).
- **CMP/Market data**: Upstox analytics token (`UPSTOX_ANALYTICS_TOKEN`) provides read-only market data. CMP cached via `CMPManager` with TTL.

## API Endpoint Patterns
New endpoints should:
1. Use `_require_active_connection_scope()` for broker-scoped data.
2. Gate writes with `require_trading_enabled` dependency.
3. Add audit logging via `log_audit()` for sensitive operations.
4. Use `ServiceError` (from `api.errors`) for structured error responses.

## Broker Connection Order
- **Upstox must be connected first** — it provides market data (CMP/OHLCV) for all operations.
- Zerodha connection depends on Upstox being active.
- UI enforces this via the `/broker-connections` stepper.
- OAuth callback endpoints must NOT require auth (use state token instead).

## Coding Guidelines
- **Imports**: three-block order — stdlib, third-party, local.
- **Type hints**: Use `typing.List`, `typing.Dict` or `tuple[...]`. Prefer concrete dicts/lists over pandas objects in return types.
- **Naming**: `snake_case` functions/vars, `PascalCase` classes, `SCREAMING_SNAKE` constants.
- **Formatting**: 4-space indent, 100-char soft limit, f-strings. Ruff configured with ignores: E402, E501, E722.
- **Error handling**: Wrap external API calls in try/except. Log with context. Return `{"error": ...}` for agent/tool APIs.
- **Data handling**: Sanitize NaN/None before calculations. Use `sanitize_for_json()` for pandas output. Prefer vectorized pandas ops.

## Testing Guidance
- Tests in `tests/` mirroring `core/`, `agent/`, `brokers/`.
- Mock broker SDKs (KiteConnect, Upstox) with fixtures mimicking real payloads.
- Freeze CMP data and holdings snapshots for deterministic tests.
- Write to `tmp_path` instead of `data/` for test isolation.
- `tests/conftest.py` has shared fixtures.

## Common Pitfalls
- Forgetting `current_session` setup in CLI commands → NoneType errors.
- Pandas NaN breaking string ops → sanitize with `str(value or "").strip()`.
- Windows shell JSON quoting: `--filters '{"P&L%": -5}'`.
- `APP_MODE=prod` requires `JWT_SECRET` and `TOKEN_ENCRYPTION_KEY`.
- Zerodha OAuth redirect URI must match exactly: `http://localhost:8000/brokers/zerodha/callback`.
- Upstox OAuth redirect URI must match exactly: `http://localhost:8000/brokers/upstox/callback`.
- `api.py` at root is legacy — `api/main.py` is the real entry point.

## Security
- Never commit `.env`, tokens, or raw CSV exports.
- Broker tokens encrypted with `TOKEN_ENCRYPTION_KEY` in DB.
- `ALLOW_INSECURE_TOKENS=1` only for dev; required `0` in prod.
