# AGENTS.md

## Repo Layout
- `api/main.py` — `create_app()`; `app` built at import time. Health probes: `/health`, `/ready`.
- `api/routes/` — registered: auth, admin, market, broker_connections, brokers (+ `zerodha_router`), session, holdings, holdings_v2, plan (+ `dynamic_avg_router`), risk, gtt, jobs, ai, entry_strategy, candidates. `holdings.py` and `holdings_v2.py` both use prefix `/holdings` (v2 holds the UI-facing per-session endpoints).
- `api/routes/sessions.py` and `api/routes/users.py` exist but are **not included in `create_app()`** — dead routers, edits have no effect.
- `api/dependencies.py` — module-level service singletons, `get_current_user`, `require_admin`, `require_trading_enabled`, `require_premium`, and all `JOB_*` constants.
- `api/errors.py` — `ServiceError` + handlers. `core/audit.py:log_audit()`.
- `core/` — trading engines; `core/services/` domain services; `core/evaluators/` per-strategy candidate evaluators; `core/runtime/` `SessionRegistry` + `JobRunner`; `core/security/` JWT + confirm tokens.
- `core/api.py` — legacy FastAPI app, not referenced anywhere. Do not extend. The `auth/` package is likewise unused (no imports, not copied into `Dockerfile`).
- `ui/src/api/client.ts` — single `ApiClient`, all endpoints as methods; base URL is `VITE_API_BASE_URL`.
- `db/models.py`, `db/database.py` (SQLite, WAL, auto-creates `data/`), `alembic/versions/`.
- `menu_cli.py`, `core/cli.py` — legacy CLI. `tools/` — ad-hoc scripts. `docs/help/*.md` — user-facing feature docs.

## Setup
```bash
python -m venv venv && venv\Scripts\activate   # deps are unpinned in requirements.txt
pip install -r requirements.txt
cp .env.example .env                           # APP_MODE=dev by default
python -m alembic upgrade head                 # DB at data/tradecraftx.db
cd ui && npm install
```
- `ui/.env` must set `VITE_API_BASE_URL=http://localhost:8000`. There is no Vite proxy, so without it `npm run dev` sends API calls to `:5173` and every request fails. `ui/.env` is gitignored.
- Dev CORS defaults allow `localhost:5173` and `:3000`; dev mode auto-provisions a user on `POST /auth/login` and skips serving `ui/dist/`.
- One-click local run: `start.bat` → `docker compose up --build -d` (built UI served at `:8000`, container runs `APP_MODE=prod` and migrates on boot).

## Commands
```bash
python -m uvicorn api.main:app --reload --port 8000
python -m alembic upgrade head
venv\Scripts\python.exe -m pytest tests/                 # ~323 tests
venv\Scripts\python.exe -m pytest tests/test_file.py::TestCls::test_method
cd ui && npm run build                                   # tsc -b && vite build → ui/dist/
```
- **Frontend gate is `npm run build` only.** `npm run lint` is broken (no `eslint` dependency or config). No UI test runner.
- Lint only what you changed: `ruff check <paths>`, `ruff format <paths>`. Repo-wide is dirty and should not be "fixed" as a side effect — `ruff check api core brokers` reports ~151 pre-existing errors (mostly W293) and `ruff format --check api core` would rewrite ~60 files.
- Ruff config: line-length 100, rules `E,F,W,I`; `E402`, `E501`, `E722` ignored. `pylint` is not installed; `.pylintrc` is a stub.
- No CI, no pre-commit hooks. Verification is manual.

## Architecture
- **DI**: services are module-level singletons in `api/dependencies.py`; tests override them via `app.dependency_overrides`.
- **Sessions are in-memory** (`SessionRegistry`, `ActiveConnectionStore` are keyed by user + broker `connection_id`). After a restart, `session_id`s are gone → "Session not found"; the UI reuses connection ids from localStorage.
- **Jobs**: `JobRunner` persists rows in `models.Job`. Adding a job type = constant in `api/dependencies.py` + handler in `_register_jobs()`. Results are fetched with `get_latest_result(session_id, job_type)`.
- **Config**: `APP_MODE=dev|prod` (legacy `DEV_MODE`/`HOSTED_MODE` still override). `load_dotenv()` runs in both `api/main.py` and `api/config.py` on purpose. In prod, missing `JWT_SECRET`/`TOKEN_ENCRYPTION_KEY` raises `ConfigError` **at import**, so `APP_MODE=prod` in `.env` breaks tests and scripts too.
- **Market data**: `UPSTOX_ANALYTICS_TOKEN` (long-lived analytics token) drives CMP/OHLCV; Upstox must connect before Zerodha. OHLCV is stored in the DB, not CSV.
- **Tunables**: `core/strategy_config.py` (`STRATEGY_*` env vars) and `core/da_config.py` (thread-safe mutable in-memory DA config, updated via API). Don't hardcode thresholds in services.

## Entry Candidate Pipeline
`core/candidates.py` (normalized models/enums) → `core/evaluators/{multi_level,dynamic_avg}.py` (one evaluator per `StrategyType`) → `core/candidate_service.py` (orchestrates, dedupes, ranks) → job `candidate_generate` → `api/routes/candidates.py`.
Glossary: **DA** = Dynamic Averaging (BUY-only, regime-based), **MLE** = Multi-Level Entry, **WROI** = weighted ROI on capital, plus swing eligibility, thesis break, market-structure revision (`core/services/`).

## Endpoint Patterns
- Broker-scoped data → `_require_active_connection_scope()`; session data → `registry.require_access(session_id, user)`.
- Write operations → `require_trading_enabled`; premium-only placement → `require_premium`.
- GTT apply/finalize → confirm-token flow (`core/security/confirm_token_store.py`).
- Sensitive ops → `log_audit()`. Errors → raise `ServiceError(error_code=..., http_status=...)`.
- OAuth callbacks (`/brokers/{zerodha,upstox}/callback`) must stay unauthenticated; state tokens handle verification.

## Database & Migrations
- Head is `008_add_swing_detail_fields`; `003` was removed deliberately (004 chains to 002) — do not recreate it.
- Schema changes need **both** a new `alembic/versions/` revision and a `db/models.py` update. The startup `Base.metadata.create_all` only creates missing tables; it never alters columns.
- `alembic/env.py` resolves the URL from `db.database` (i.e. `DATABASE_URL`), so `alembic.ini`'s `sqlalchemy.url` is ignored when the env var is set.
- `db/migrations/` is legacy and not wired to Alembic.

## Testing
- `tests/conftest.py`: in-memory SQLite + `dependency_overrides` for DB, session manager/registry, broker connection/auth-state, auth service, job runner. `create_app()` runs at import, but the TestClient is not used as a context manager, so startup hooks don't fire.
- Mock broker SDKs (KiteConnect, Upstox); freeze CMP/holdings snapshots; write files to `tmp_path`. Tests mirror `core/`, `brokers/`, `api/` by topic, flat in `tests/`.

## Security
- Never commit `.env`, tokens, or raw CSV/XLSX exports (`.gitignore` covers them, plus `data/*.db*`).
- `TOKEN_ENCRYPTION_KEY` (base64url 32-byte) and a non-default `JWT_SECRET` are required in prod; `ALLOW_INSECURE_TOKENS=1` is dev-only.
- Broker redirect URIs must match exactly: `http://localhost:8000/brokers/{zerodha,upstox}/callback` (Render uses `https://<app>.onrender.com/...`).

## Pitfalls
- `npm run lint` does not work; `pylint` is not installed.
- Pandas NaN breaks string ops → `str(value or "").strip()`; use `core/utils.py:sanitize_for_json()` for DataFrame/NaN output.
- Legacy CLI (`menu_cli.py`, `core/api.py`) needs `current_session` set or hits NoneType errors — prefer the API.
- Windows shell JSON filters need single quotes: `--filters '{"P&L%": -5}'`.
- `APP_MODE=prod` requires `JWT_SECRET` + `TOKEN_ENCRYPTION_KEY` + `DATABASE_URL`; `docker-compose.yml` ships insecure placeholders for local use only.
- `requirements.txt` is unpinned — Docker/CI installs can drift from the local venv.
- Deployment is Render via `render.yaml` (Dockerfile, SQLite on a persistent disk); the image does not copy `auth/`.
