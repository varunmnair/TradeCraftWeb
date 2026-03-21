# AGENTS.md

## Purpose
- TradeCraftX is an API-first application with a web UI as the primary user interface.
- This document provides autonomous agents the minimum context they need to work safely.
- The CLI exists for legacy workflows, debugging, or developer convenience only.

## Repository Layout
- `api/`: FastAPI backend; handles authentication, sessions, jobs, and core trading workflows.
- `ui/`: React UI built with Vite; the primary user interaction layer.
- `core/`: Trading engines: CLI commands, risk management, CMP cache, session cache, holdings analytics, entry planners.
- `brokers/`: Broker adapters (`ZerodhaBroker`, `UpstoxBroker`) plus `BrokerFactory`.
- `agent/`: AI-facing helpers (LLM provider, strategy agent loop, tool registry).
- `data/`: CSV inputs (tradebooks, ROI history, entry levels). Gitignored for sensitive data.
- `auth/`: Cached broker tokens. Treat as sensitive, do not commit.

## Environment & Setup
- **Python**: 3.10+ with venv: `python -m venv venv && venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Unix).
- **Node.js**: v18+ for frontend.
- **Backend deps**: `pip install -r requirements.txt`
- **Frontend deps**: `npm install` in `ui/`
- **Env files**: Copy `.env.example` to `.env` - keys: `KITE_API_KEY`, `UPSTOX_API_KEY`, `JWT_SECRET`, `TOKEN_ENCRYPTION_KEY`, etc.
- **Linting**: `.pylintrc` for backend; ESLint for frontend.

## Primary Commands

### Backend
```bash
# Run API server
python -m uvicorn api.main:app --reload --port 8000

# Run with production mode (for testing OAuth callbacks)
APP_MODE=prod python -m uvicorn api.main:app --reload

# CLI workflow
python menu_cli.py

# Direct Typer command
python -m typer core.cli -- list-entry-levels
```

### Frontend
```bash
cd ui
npm run dev      # Development server at localhost:5173
npm run build    # Production build
npm run preview # Preview production build
```

### Testing
```bash
# Run all tests
python -m pytest -q

# Run single test
python -m pytest tests/test_holdings.py::TestHoldingsAnalyzer::test_filters

# Run tests matching keyword
python -m pytest tests/ -k keyword

# Lint backend
python -m pylint api core brokers
```

## Architecture Highlights
- **API-first**: FastAPI handles auth, sessions, jobs, trading workflows.
- **Session management**: `SessionCache` centralizes holdings, entry levels, CMP/GTT caches with TTL refresh.
- **Broker adapters**: `brokers/zerodha_broker.py` and `brokers/upstox_broker.py` normalize return structures.
- **Job-based async**: Long-running tasks use job queue pattern.
- **Active broker connection**: Use `_require_active_connection_scope()` for endpoints instead of session_id.

## API Endpoints Pattern
New endpoints should:
1. Use `_require_active_connection_scope()` for broker-scoped data
2. Include trading gate via `require_trading_enabled` dependency for write operations
3. Add audit logging via `log_audit()` for sensitive operations

## Coding Guidelines

### Imports (three-block order)
```python
# 1. Stdlib
import os
import json
from typing import List, Dict

# 2. Third-party
import pandas as pd
from fastapi import APIRouter, Depends

# 3. Local
from api.dependencies import get_current_user
from core.auth.context import UserContext
```

### Type Hints
- Use `typing.List`, `typing.Dict`, `tuple[...]` for function signatures.
- Prefer returning concrete dicts/lists instead of pandas objects.
- Example: `def get_holdings() -> List[Dict[str, Any]]`

### Naming Conventions
- `snake_case` for variables/functions
- `PascalCase` for classes
- `SCREAMING_SNAKE` for constants (e.g., `DEFAULT_CONFIG`)

### Formatting
- 4-space indentation, no trailing whitespace
- 100-character soft limit
- Use f-strings for interpolation

### Error Handling
- Wrap external API calls in try/except
- Log errors with context (broker, symbol, user_id)
- Return dict with `error` key for agent/tool APIs
- Never swallow exceptions silently

### Logging vs Print
- CLI UX can use print/emojis for humans
- Background code uses `logging` module
- Log exceptions with context, then raise

### Data Handling
- Sanitize NaN/None before calculations
- Use `sanitize_for_json()` when pandas might introduce NaN/inf
- Normalize column names (strip, lower/replace spaces) before calculations
- Prefer vectorized pandas operations over loops

## Testing Guidance
- Use `pytest` - place tests in `tests/` mirroring `core/`, `agent/`, `brokers/`
- Mock broker SDKs (KiteConnect, Upstox) - use fixtures that mimic payloads
- Freeze CMP data and holdings snapshots for deterministic tests
- Write to `tmp_path` instead of `data/` for test isolation

## Common Pitfalls
- Forgetting `current_session` setup in CLI commands → NoneType errors
- Pandas NaN values breaking string operations → sanitize with `str(value or "").strip()`
- Windows shell JSON quoting: `--filters '{"P&L%": -5}'`
- OAuth callback endpoints must NOT require auth (use state token instead)

## Security
- Never commit `.env`, tokens, or raw CSV exports
- Use `APP_MODE=prod` in production (not `DEV_MODE=true`)
- Broker redirect URIs must match exactly in code and developer portal

## Cursor / Copilot Rules
- No `.cursor/rules` or `.github/copilot-instructions.md` files exist
