# TradeCraftX

TradeCraftX is a self-hostable web application for Indian equity traders using **Zerodha (Kite)** and **Upstox**. It connects to brokers over OAuth, stores encrypted broker tokens, analyses holdings, generates structured buy-entry plans, manages GTT (Good Till Triggered) orders, and offers an optional AI analyst backed by Google Gemini or Groq.

> **Disclaimer:** TradeCraftX helps you analyse and execute a plan; you remain responsible for every trading decision. Order placement and modification always require an explicit confirmation.

## Features

- **Multi-broker support** — connect Zerodha and Upstox with OAuth; broker-scoped data and trading actions are tied to the active connection.
- **Holdings analysis** — ROI, weighted ROI (WROI), ROI/day, trade history, filters, and CSV export.
- **Entry strategies** — Multi-Level Entry (MLE) and regime-based Dynamic Averaging (DA, buy-only), with candidate generation, review/revision, swing eligibility, thesis-break checks, and market-structure revisions.
- **GTT management** — preview, confirm, and apply changes; delete stale orders and normalise trigger variance.
- **Risk controls** — optional risk adjustments to an entry plan and a premium/trading-enabled gate before live placement.
- **AI Analyst** — ask questions about holdings, entries, and pending orders (suggestions only; actions still need confirmation).
- **Jobs & audit** — long-running work runs through a persisted job runner with status monitoring; sensitive operations are audited and use confirm tokens.
- **Multi-user auth** — JWT access tokens, refresh cookies, admin/user roles, and per-user broker connections.

## Architecture

| Path | Purpose |
| --- | --- |
| `api/main.py` | FastAPI app factory (`create_app()`), health probes, CORS, static UI hosting |
| `api/routes/` | HTTP routers: auth, admin, brokers, broker connections, session, holdings, plan, risk, gtt, jobs, ai, entry strategy, candidates, market |
| `api/dependencies.py` | Module-level service singletons, auth helpers, job type constants |
| `core/` | Trading engines and domain services (`core/services/`), strategy evaluators (`core/evaluators/`), runtime session registry and job runner (`core/runtime/`), security helpers (`core/security/`) |
| `db/` | SQLAlchemy models and SQLite database helpers |
| `alembic/` | Schema migrations (head: `008_add_swing_detail_fields`) |
| `ui/` | React 18 + TypeScript + Material UI frontend (Vite); single API client at `ui/src/api/client.ts` |
| `tests/` | pytest suite (~323 tests) with mock broker SDKs and in-memory SQLite |
| `docs/help/` | User-facing feature guides rendered by the in-app Help panel |

Legacy entry points (`menu_cli.py`, `core/cli.py`, `core/api.py`, `auth/`) still exist but are not part of the web application. Prefer the API/UI.

## Prerequisites

- Python 3.10+ (the Docker image uses Python 3.11) and Node.js 18+ if running the UI separately
- Docker Desktop for the one-click Docker path
- Zerodha and/or Upstox developer app credentials; an **Upstox Analytics** app/token is required for CMP/OHLCV market data
- Optional: Google Gemini and/or Groq API keys for the AI Analyst

## Quick start (Docker)

```bash
git clone https://github.com/varunmnair/TradeCraftWeb.git
cd TradeCraftWeb
cp .env.example .env          # Windows: copy .env.example .env
```

Fill in at least `UPSTOX_API_KEY`, `UPSTOX_API_SECRET`, and `UPSTOX_ANALYTICS_TOKEN`; add the Zerodha keys if you plan to use Kite. Generate the two production secrets locally and paste them into `.env`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"   # TOKEN_ENCRYPTION_KEY
python -c "import secrets; print(secrets.token_urlsafe(48))"   # JWT_SECRET
```

Then start the app:

- **Windows:** double-click `start.bat` (checks `.env`, waits for `/health`, opens `http://localhost:8000`)
- **Any platform:** `docker compose up --build -d`

Docker builds the React UI, runs `alembic upgrade head`, and serves the built app and API together on port 8000. SQLite data lives in the `app_data` named volume.

> `docker-compose.yml` ships with placeholder `JWT_SECRET`, `ALLOW_INSECURE_TOKENS=1`, and `COOKIE_SECURE=0` for local use only. Replace these before exposing the service.

## Development setup

### Backend

```bash
python -m venv venv
venv\Scripts\activate                 # source venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env                  # Windows: copy .env.example .env; APP_MODE=dev by default
python -m alembic upgrade head        # creates data/tradecraftx.db
python -m uvicorn api.main:app --reload --port 8000
```

In dev mode the API falls back to a dev user (`dev@tradecraftx.local`, admin, trading enabled) when no bearer token is sent, and it does **not** serve `ui/dist/`; run Vite separately. Error responses include full details in dev and are sanitised in prod.

### Frontend

```bash
cd ui
npm install
cp .env.example .env                  # Windows: copy .env.example .env; sets VITE_API_BASE_URL
npm run dev                           # http://localhost:5173
```

There is no Vite proxy: `ui/.env` must set `VITE_API_BASE_URL=http://localhost:8000`, otherwise the browser sends API calls to port 5173 and every request fails. `ui/.env` is gitignored.

To verify the production build: `npm run build` (`tsc -b && vite build` → `ui/dist/`). `npm run lint` is currently broken (no ESLint dependency/config) — the build is the frontend gate.

## Configuration

All backend settings are read from `.env` (or the process environment) by `api/config.py`. Tunable analysis thresholds live in `core/strategy_config.py` (`STRATEGY_*`) and `core/da_config.py` (`DA_*`, mutable at runtime via the API).

| Variable | Notes |
| --- | --- |
| `APP_MODE` | `dev` (default) or `prod`. Legacy `DEV_MODE` / `HOSTED_MODE` still override it. |
| `DATABASE_URL` | Defaults to `sqlite:///./data/tradecraftx.db`; required in prod. |
| `KITE_API_KEY`, `KITE_API_SECRET`, `KITE_REDIRECT_URI` | Zerodha credentials and redirect URI. |
| `UPSTOX_API_KEY`, `UPSTOX_API_SECRET`, `UPSTOX_REDIRECT_URI` | Upstox credentials and redirect URI. |
| `UPSTOX_ANALYTICS_TOKEN` | Long-lived read-only token for CMP/OHLCV; create an Analytics app in the Upstox developer portal. |
| `JWT_SECRET`, `TOKEN_ENCRYPTION_KEY` | Required in prod: a strong random secret and a base64url-encoded 32-byte key. |
| `ALLOW_INSECURE_TOKENS` | Dev only; allows prod-like startup without encryption key. Keep `0` in production. |
| `COOKIE_SECURE`, `COOKIE_SAMESITE` | Refresh-cookie settings; `COOKIE_SECURE` defaults to true in prod. |
| `BOOTSTRAP_ADMIN_EMAIL` | Promotes an existing registered user to admin at startup. |
| `GEMINI_API_KEY`, `GROQ_API_KEY` | Optional AI provider keys. |
| `CORS_ALLOWED_ORIGINS` | Comma-separated origins. Dev defaults to localhost:5173/3000 (and 127.0.0.1 variants); set explicitly in prod. |

> `APP_MODE=prod` validates required config **at import time**. Setting it in `.env` will also break local test and script runs unless `JWT_SECRET`, `TOKEN_ENCRYPTION_KEY` (or `ALLOW_INSECURE_TOKENS=1`), and `DATABASE_URL` are present.

## Connecting brokers

1. Register the redirect URIs **exactly** as they appear in your config (local): `http://localhost:8000/brokers/upstox/callback` and `http://localhost:8000/brokers/zerodha/callback`. For Render use `https://<your-app>.onrender.com/...`. Any mismatch fails the OAuth flow.
2. Open `/broker-connections` in the UI and connect **Upstox first** — it supplies CMP/OHLCV market data used by the analysis flows. The UI stepper enforces this order and polls connection status.
3. Complete the consent screen in the broker's window; the callback page confirms success. API equivalents: `GET /brokers/upstox/connect` and `GET /brokers/zerodha/connect` with `Authorization: Bearer <token>` (callbacks themselves are unauthenticated).
4. Create a session on `/sessions` (or `POST /session/start` with `broker_connection_id`). Connection IDs are kept in localStorage as `tradecraftx_upstox_connection_id` and `tradecraftx_zerodha_connection_id`.

Sessions are in-memory: after an API restart, old `session_id`s are gone ("Session not found"). Start a new session; connection IDs are reused from localStorage. Tokens also expire — reconnect a broker if actions start failing with invalid-token errors.

## Typical daily workflow

1. **Holdings** → refresh/analyze, sort by ROI/day, filter underperformers, export a snapshot.
2. **Buy / Entries → Multi-Level Entry** → generate candidates, review E1/E2/E3 levels, select only the stocks you want, place with confirmation. Optionally apply risk adjustments.
3. **Buy / Entries → Dynamic Averaging** → generate averaging candidates for existing holdings and place selected top-ups.
4. **GTT Orders** → review pending broker orders, delete stale ones, or normalise variance to a target (for example 2%).
5. **AI Analyst** → ask follow-up questions; suggestions never place orders without your confirmation.

See `docs/help/index.md` (and the other guides in `docs/help/`) for the full screen-by-screen guide.

## API notes

- Interactive docs: `/docs` and `/redoc`; OpenAPI schema: `/openapi.json`.
- `GET /health` (liveness, includes API version) and `GET /ready` (DB check; 503 if unavailable or the prod encryption key is missing).
- Auth: `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me`.
- Responses include an `X-Request-ID` header (inbound `X-Request-ID` is preserved); the same ID appears in logs.
- Errors use a consistent shape with an `error_code` (for example `session_not_found`, `invalid_token`) and appropriate HTTP status.
- Long operations return job IDs; poll via the jobs endpoints or watch the Jobs page. Job types include `holdings_analyze`, `plan_generate`, `candidate_generate`, `gtt_preview`, `gtt_apply`, `trades_sync`, `ohlcv_refresh`, and others.

## Tests, lint, and formatting

```bash
venv\Scripts\python.exe -m pytest tests/
venv\Scripts\python.exe -m pytest tests/test_file.py::TestCls::test_method
ruff check <changed paths>          # line length 100, rules E/F/W/I
ruff format <changed paths>
cd ui && npm run build
```

Only lint/format files you changed — repo-wide lint and format are known to be dirty. There is no CI, no pre-commit hooks, and no UI test runner.

## Deployment

The `Dockerfile` performs a multi-stage build (Node → React bundle, then Python → FastAPI) and does not copy `auth/` or the tests. `render.yaml` defines a Render Docker web service using the same image; set secrets as environment variables in the Render dashboard, mount a persistent disk at `/app/data` for SQLite, and update both broker redirect URIs to your Render hostname. See `docs/render-deploy.md` for the step-by-step guide and `docs/checklists/local-prod-smoke.md` for a production smoke test.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| UI loads but every API call fails | `ui/.env` must contain `VITE_API_BASE_URL=http://localhost:8000`; restart Vite after changing it. |
| `ConfigError` on startup or during tests | Prod mode requires `JWT_SECRET`, `TOKEN_ENCRYPTION_KEY` (or `ALLOW_INSECURE_TOKENS=1`), and `DATABASE_URL`. Unset `APP_MODE=prod` for local dev/tests. |
| CMP/OHLCV and market-data features fail | `UPSTOX_ANALYTICS_TOKEN` is missing, invalid, or still a placeholder. |
| "Session not found" | Sessions are in-memory only; start a new session after an API restart. |
| Broker OAuth fails immediately | Redirect URI must match the developer-console entry character-for-character. |
| CORS errors in the browser | Add the UI origin to `CORS_ALLOWED_ORIGINS` in prod; dev defaults cover localhost:5173/3000. |
| `GET /ready` returns 503 | Database unreachable, or prod token encryption key missing. Check logs and `DATABASE_URL`. |
| `npm run lint` fails | Known: ESLint is not installed/configured. Use `npm run build` as the frontend check. |

## Documentation

- `docs/help/index.md` — in-app help content: concepts, daily workflow, screen guide, safety tips
- `docs/help/{holdings,buy-entries,gtt-orders,ai-analyst}.md` — focused feature guides
- `docs/render-deploy.md` — deployment instructions
- `docs/checklists/local-prod-smoke.md` — production verification checklist
- `AGENTS.md` — repository conventions and internal architecture notes

## Security

Never commit `.env`, broker tokens, session pickles, or raw CSV/XLSX exports. Use strong, unique secrets in production, keep `ALLOW_INSECURE_TOKENS=0`, and restrict CORS to your own origins. Trading is disabled by default for newly registered users and must be enabled by an admin.
