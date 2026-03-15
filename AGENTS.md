# AGENTS.md

## Purpose
- TradeCraftX is now an API-first application with a web UI as the primary user interface.
- This document provides autonomous agents the minimum context they need to work safely, capturing current commands, data dependencies, and coding expectations to ensure consistency with the production workflow.
- The CLI exists for legacy workflows, debugging, or developer convenience only.
- This file intentionally focuses on day-to-day engineering needs (commands, style, architecture) and not business or strategy secrets.

## Repository Layout (quick mental map)
- `api/`: FastAPI backend; handles authentication, sessions, jobs, and core trading workflows.
- `ui/`: React UI built with Vite; the primary user interaction layer.
- `menu_cli.py` and `core/cli.py`: Legacy / optional tooling for interactive CLI workflows, debugging, or developer convenience.
- `core/`: Holds the trading engines: CLI commands, risk management, CMP cache, session cache, holdings analytics, entry planners, and shared utilities.
- `brokers/`: Defines broker adapters (`ZerodhaBroker`, `UpstoxBroker`) plus the `BrokerFactory` that core logic relies on.
- `agent/`: Hosts AI-facing helpers (LLM provider, strategy agent loop, tool registry) that plug into `core.cli.ask_ai_analyst` and EntryPilot.
- `data/`: is gitignored for most files and stores CSV inputs (tradebooks, ROI history, entry levels) plus the shared `Name-symbol-mapping.csv`.
- `auth/`: Keeps cached access tokens per broker; treat it as sensitive and do not commit anything inside.
- Misc helpers (`setup.*`, `run.*`, `requirements.txt`, `.env.example`) live at the repo root; there is no `pyproject.toml` or Poetry config.

## Environment & Setup
- Supported runtime: Python 3.10+ for backend, Node.js v18+ for frontend. System dependencies include pandas, kiteconnect, upstox SDK, Typer, FastAPI for backend; npm/yarn for frontend.
- Always create/activate the local venv for backend to avoid colliding with host Python: `python -m venv venv && venv\Scripts\activate` (Windows) or `python3 -m venv venv && source venv/bin/activate` (Unix).
- Install backend dependencies via `pip install -r requirements.txt`; re-run after any dependency change.
- Install frontend dependencies via `npm install` in the `ui/` directory.
- Populate `.env` (backend) and `.env.local` (frontend) by copying their respective `.example` files; required keys: `KITE_API_KEY`, `KITE_API_SECRET`, `KITE_REDIRECT_URI`, `UPSTOX_API_KEY`, `UPSTOX_API_SECRET`, `UPSTOX_REDIRECT_URI`, `GEMINI_API_KEY`, `GROQ_API_KEY`.
- Token refresh relies on `auth/kite_access_token.pkl` and `auth/upstox_access_token.pkl`; SessionManager regenerates them interactively via browser prompts when missing/expired.
- Data CSV naming matters: `data/{USER_ID}-{broker}-entry-levels.csv`, `data/{USER_ID}-{broker}-tradebook.csv`, `data/{USER_ID}-{broker}-roi-data.csv`. Keep headers consistent (see README).
- `.pylintrc` is used for backend linting; frontend linting/formatting handled by Vite/ESLint configuration.

## Primary Commands (build, lint, test, run)
- **Bootstrap**: `setup.bat` / `setup.sh` orchestrate venv creation + `pip install`. These scripts are idempotent and safe to rerun.
- **CLI workflow**: Activate the venv and run `python menu_cli.py`. This opens the broker selection wizard and loops through Typer commands using `CliRunner`.
- **Direct Typer command**: `python -m typer core.cli -- list-entry-levels --filter-ltp 500` (Typer expects a `--` before command args on Windows shells).
- **Single command without menu**: `python -m typer core.cli analyze-holdings --filters '{"P&L%": -5}' --sort-by "ROI/Day"`.
- **Generate entry plan only**: `python -m typer core.cli list-entry-levels` followed by `python -m typer core.cli apply-risk-management` and `python -m typer core.cli place-gtt-orders` as needed.
- **Dynamic averaging planner**: `python -m typer core.cli plan-dynamic-avg` then `python -m typer core.cli place-dynamic-averaging-orders`.
- **AI analyst shell**: Start `menu_cli.py`, initialize a broker session, then choose option 4 or run `python -m typer core.cli ask-ai-analyst` (requires `GEMINI_API_KEY`).
- **Build/start REST services**: none today; FastAPI + Uvicorn appear in requirements for future work but no `uvicorn` entry point exists yet.
- **Linting**: `python -m pylint menu_cli.py core agent brokers` (respects `.pylintrc`). Keep lint noise low by stubbing network calls in tests.
- **Ad-hoc formatting**: use `ruff format` or `black` only if the project adopts them; otherwise follow the manual rules in *Coding Guidelines*.
- **Tests**: Tests exist under `tests/` using pytest. Run all tests with `python -m pytest -q` from repo root.
- **Run a single test**: `python -m pytest tests/test_holdings.py::TestHoldingsAnalyzer::test_filters` (replace with actual module/class/case).
- **Run tests matching keyword**: `python -m pytest tests/ -k keyword` for quick loops.
- **Smoke script**: `python menu_cli.py --log-level DEBUG` quickly exercises login, cache refresh, and plan generation.

## Legacy / Optional CLI
- **CLI workflow**: Activate the venv and run `python menu_cli.py`. This opens the broker selection wizard and loops through Typer commands using `CliRunner`.
- **Direct Typer command**: `python -m typer core.cli -- list-entry-levels --filter-ltp 500` (Typer expects a `--` before command args on Windows shells).
- **Single command without menu**: `python -m typer core.cli analyze-holdings --filters '{"P&L%": -5}' --sort-by "ROI/Day"`.
- **Generate entry plan only**: `python -m typer core.cli list-entry-levels` followed by `python -m typer core.cli apply-risk-management` and `python -m typer core.cli place-gtt-orders` as needed.
- **Dynamic averaging planner**: `python -m typer core.cli plan-dynamic-avg` then `python -m typer core.cli place-dynamic-averaging-orders`.
- **AI analyst shell**: Start `menu_cli.py`, initialize a broker session, then choose option 4 or run `python -m typer core.cli ask-ai-analyst` (requires `GEMINI_API_KEY`).

## Data & Secrets Handling
- Never commit populated `.env`, token pickle files, or raw CSV exports; `.gitignore` already covers them but double-check before staging.
- When generating or modifying CSVs, use `core.utils.write_csv` so the column ordering and numeric handling stay uniform; manual writes often corrupt case/float precision.
- `Name-symbol-mapping.csv` is very large; load via pandas and filter columns before iterating to keep memory manageable.
- Broker APIs rate-limit aggressively; prefer batch methods (`CMPManager._fetch_bulk_quote_upstox`) instead of per-symbol calls.
- Sensitive env vars (API keys, tokens) should be read with `os.getenv` at import time like `SessionManager` already does; avoid caching secrets in globals other than the provided pickles.

## Architecture Highlights
- `core.session.SessionCache` centralizes all broker data (holdings, entry levels, CMP cache, GTT cache) with a TTL refresh strategy; always access holdings/entry levels/quotes through it to stay in sync.
- `core.session_manager.SessionManager` owns credential loading + token validation for both brokers and is injected into brokers and CMPManager.
- `core.cli` exposes Typer commands; almost every CLI action assumes `core.cli.current_session` has been set via `set_current_session`, so new commands must respect that contract.
- Entry workflows: `MultiLevelEntryStrategy` (`core/multilevel_entry.py`) builds candidates → `GTTManager` places/deletes/adjusts orders → `SessionCache` rewrites the cached plan at `data/gtt_plan_cache.json`.
- Risk controls: `core.risk_manager.RiskManager` computes ATR, volatility, and shock-drop guards; it feeds adjustments back into multi-level planners and the dynamic averaging planner.
- Dynamic averaging: `core.dynamic_avg.DynamicAveragingPlanner` piggybacks on holdings data and entry-level metadata (DA columns) to schedule top-up GTTs.
- Analytics: `core.holdings.HoldingsAnalyzer` populates tradebooks and ROI CSVs, applies filters/sorting, and calculates ROI metrics + trend detection.
- CMP caches: `core.cmp.CMPManager` collects symbols from holdings/GTTs/entry levels, fetches Upstox quotes in batches, and optionally fetches historical candles for TA-driven features (EntryLevelReviser, RiskManager).
- Agent system: `agent/manager.py`, `agent/core.py`, and `agent/tools.py` implement a lightweight plan → tool → summarize loop using Google Gemini; `agent/strategy_agent.py` hosts EntryPilot for interactive query planning.
- Brokers: `brokers/zerodha_broker.py` and `brokers/upstox_broker.py` wrap vendor SDKs and normalize return structures so the rest of the code can treat orders, holdings, and trades consistently.
- Utilities: `core/utils.py` (logging, table printing, CSV helpers) plus `core/session_singleton.py` (shared cache) reduce boilerplate for scripts/tests.

## API-first Architecture
- FastAPI backend orchestrates API requests, managing authentication, sessions, and core trading workflows.
- Multi-user SaaS readiness is supported through robust authentication, tenant management, and broker connection handling.
- Job-based asynchronous workflows are the primary execution model, handling long-running tasks efficiently.
- UI + API flows have replaced interactive CLI menus for most user interactions.

## Broker-Specific Notes
- Zerodha connection via the API (`/brokers/zerodha/connect`) requires an active Upstox connection for the same user first. This is because the system relies on Upstox for instrument master lists and other market data functions that are more accessible via its API.
- Zerodha paths assume `KiteConnect` session objects; never instantiate a new Kite client with raw API keys when `SessionManager` already set tokens.
- Upstox adapters depend on REST calls (requests) plus bearer tokens; `_fetch_bulk_quote_upstox` regenerates tokens when UDAPI100050 is returned—respect that flow instead of embedding manual HTTP calls elsewhere.
- Both brokers map holdings/trade payloads into normalized dicts (keys: `tradingsymbol`, `quantity`, `average_price`, `last_price`, etc.); if you extend broker data, ensure `SessionCache` and analytics modules can tolerate missing keys.
- `BrokerFactory.get_broker` is the only sanctioned creation path; pass `user_id` plus config dict and avoid storing broker instances globally.
- Broker classes expose helper constants (`TRANSACTION_TYPE_BUY`, `ORDER_TYPE_LIMIT`, etc.) because Typer commands expect them; reuse these values when building orders.
- Always call `broker.login()` before relying on remote data; `menu_cli` handles this automatically, but scripts/tests must do it explicitly or mock it out.
- The new API flow (`/session/start`) handles broker login as part of session initialization, using tokens stored via the `/brokers/{broker}/callback` flow.

## Entry & Risk Flow Walkthrough
- Entry planners start from `SessionCache.get_entry_levels()`; each row must include `symbol`, `Allocated`, `entry1-3`, `exchange`, `Quality`, and optional DA columns.
- `MultiLevelEntryStrategy.identify_candidates` filters out symbols with existing GTTs, trades executed today, or invalid allocations before quoting CMP data.
- `generate_plan` determines which level is actionable, computes spendable amounts, enforces LTP-trigger variance, and stores `original_amount` for later risk recalcs.
- `RiskManager.assess_risk_and_get_adjustments` reads ATR, RSI, ADX, and price gaps to scale amounts, enforce reserves, or cap per-level exposure.
- `GTTManager.place_orders` translates the plan into broker-specific GTT payloads and refreshes caches so immediately subsequent analyses see the new orders.
- `DynamicAveragingPlanner` reuses the multi-level helper to adjust trigger/price pairs for gradual averaging; it splits buys across `DA legs` and enforces entry-level budget checks.
- `EntryLevelReviser` fetches ~90 days of historical candles via `SessionCache.get_historical_data`, computes indicators, and rewrites per-symbol entry suggestions (E1–E3) after 30-day staleness checks.

## Data Files Reference
- `data/{user}-{broker}-tradebook.csv`: columns include `symbol`, `isin`, `trade_date`, `exchange`, `segment`, `trade_type`, `quantity`, `price`, `trade_id`, etc.; holdings analysis filters for BUY trades and reconstructs holding ages.
- `data/{user}-{broker}-roi-data.csv`: appended daily by `HoldingsAnalyzer.write_roi_results`; schema uses friendly column names (`Invested Amount`, `Absolute Profit`, `ROI per day`).
- `data/{user}-{broker}-entry-levels.csv`: curated manually; key columns `Allocated`, `entry1`, `entry2`, `entry3`, `DA Enabled`, `DA Legs`, `DA E{n} Buyback`, `Quality`, `Last Updated`.
- `data/gtt_plan_cache.json`: ephemeral cache storing the most recent draft plan. Delete it whenever plans become stale or after order placement to avoid accidental reuse.
- `data/Name-symbol-mapping.csv`: reference file for ISIN lookup; keep uppercase column headers (`SYMBOL`, `ISIN NUMBER`) intact for `CMPManager._get_instrument_key`.
- Sample fixture files under `data/` double as manual smoke data; tests should copy them into `tmp_path` rather than writing in-place.

## Development Workflow Expectations
- New commands or planners must expose Typer-friendly interfaces and, when feasible, should be callable both from `menu_cli` flows and via direct CLI invocation.
- Keep business logic outside Typer command functions (e.g., create helper classes under `core/`) so they are testable without invoking CLI state.
- When editing CLI flows, update prompts/emojis in `menu_cli.py` to keep user guidance coherent.
- Respect `SessionCache.ttl`; if your logic needs fresh data, call `refresh_all_caches()` or the specific refresh method, but avoid bypassing caches unless necessary.
- Document new environment variables or CSV columns inside README + this file so future agents pick them up automatically.
- Prefer small, reviewable commits grouped by feature; describe both intent and any risk-limiting guardrails added.
- New features should be exposed via APIs first. The UI is the primary consumer; CLI support is optional and secondary. Emphasize OpenAPI contracts as the source of truth.

## Common Pitfalls
- Forgetting to set `core.cli.current_session` before invoking Typer commands in scripts/tests leads to `NoneType` errors—mock the session or reuse `SessionCache` from `session_singleton`.
- Pandas `NaN` values coming from CSVs read as floats can break string operations; sanitize inputs (e.g., `str(value or "").strip()`).
- Upstox GTT payloads require exchange-specific instrument keys; ensure `CMPManager` has refreshed after you change entry levels, otherwise CMP lookups return `None` and planners skip symbols.
- `menu_cli` uses blocking `input()` calls; background tasks or tests should avoid calling `main_menu()` directly unless you mock stdin.
- `EntryLevelReviser` assumes `Last Updated` uses `%d-%b-%y`; invalid formats raise warnings and default to revise-everything behavior. Normalize dates when touching CSVs.
- Windows shells require quoting JSON arguments (`--filters '{"P&L%": -5}'`); forgetting the extra quotes leads to Typer parse errors.

## Review Checklist
- Confirm lint (`python -m pylint ...`) and, when added, tests (`python -m pytest`) pass locally before submitting patches.
- Scan `git status` for accidental CSV/token/venv files; never stage files under `auth/` or production CSV exports with live trades.
- When touching planner logic, run `python menu_cli.py --log-level DEBUG` and manually step through options 1–3 to ensure plan/holdings outputs still render.
- Double-check `requirements.txt` whenever you add imports. If a dependency is optional (dev-only), note it in README instead of committing a partially configured dependency.
- Update this AGENTS guide whenever you add repo-wide conventions (new commands, formatting tools, env vars) so future agents stay aligned.

## Coding Guidelines
- **Imports**: Follow three-block order (stdlib, third-party, local). Keep Typer-specific imports (`import typer`) near the top of CLI modules; avoid wildcard imports.
- **Type hints**: Use `typing.List`, `typing.Dict`, `tuple[...]` etc. for function signatures that return structured data (`GTTManager.analyze_gtt_buy_orders`). Prefer returning concrete dicts/lists instead of pandas objects.
- **Formatting**: 4-space indentation, no trailing whitespace, 100-character soft limit. Use f-strings for interpolation; prefer descriptive unicode icons only in CLI output (not logs).
- **Logging vs print**: CLI UX can print emojis/messages for humans. Background code uses `logging` with `setup_logging` so menu log level flag works. Log exceptions with context, then raise or signal errors to CLI (avoid bare prints inside brokers/managers).
- **Errors**: Wrap external API calls in `try/except`, log errors with broker/symbol context, and bubble actionable messages upward. Never swallow exceptions silently; at minimum return a dict with an `error` key for agent/tool APIs.
- **State management**: Do not instantiate new brokers or SessionManagers inside hot paths; reuse the session-bound instances to preserve cached tokens and CMP data.
- **Data handling**: Sanitize NaN/None before calculations. Use helper methods (`_is_valid_price`, `sanitize_for_json`) instead of repeating checks. When modifying CSV schema, update both readers (`read_csv`) and writers (`write_csv`).
- **Pandas usage**: Always normalize column names (strip, lower/replace spaces) before calculations, as done in `core.holdings`. Prefer vectorized operations over loops unless you need imperative logic.
- **CLI interactions**: Use Typer options (`typer.Option`) for new parameters; update `menu_cli.py` to surface new flows via `runner.invoke` when appropriate.
- **Agents & tools**: Keep prompts declarative and enforce JSON outputs (`response_mime_type="application/json"`) like `agent.core.Agent`. Any new tool must be registered in `ToolRegistry.get_tools` and described in `get_definitions`.
- **Network calls**: Centralize Upstox/Zerodha HTTP requests inside brokers or CMPManager; do not hit broker APIs from random modules. Respect batching and token regeneration hooks already present.
- **Naming conventions**: snake_case for variables/functions, PascalCase for classes, SCREAMING_SNAKE for constants (e.g., `DEFAULT_CONFIG`). Align CSV column casing with existing files (e.g., `Symbol`, `Invested`).
- **Return values**: Prefer simple dict/list structures that serialize cleanly for Typer output or JSON logs. Use `sanitize_for_json` when pandas might introduce NaN/inf.

## Agent & LLM Patterns
- `agent.llm_provider.LLMProvider` lazily instantiates a Google Generative AI client; respect this singleton to avoid socket exhaustion.
- EntryPilot loops (planner → tool → observation) rely on a working GTT plan cached via SessionCache; ensure `core.cli.list_entry_levels` ran before invoking EntryPilot.
- When adding prompts, keep them deterministic and include tool schema; parse responses defensively (`json.loads` wrapped in try/except) and surface failures to the user with actionable copy.
- Never store LLM responses verbatim in git; if you need test fixtures, scrub secrets and comply with provider policies.

## Testing & Verification Guidance
- There is no automated suite yet; when you add tests favor `pytest` and structure modules under `tests/` mirroring `core/`, `agent/`, and `brokers/`.
- Mock broker SDKs (KiteConnect, Upstox) so CI does not depend on external APIs; simple dataclasses or fixtures that mimic holdings/GTT payloads work well.
- For planners, assert on deterministic outputs by freezing CMP data (`SessionCache.cmp_manager.cache`) and holdings snapshots loaded from sample CSVs in `tests/fixtures/`.
- Use `python -m pytest tests/... -k keyword` for quick loops; keep tests hermetic by writing to `tmp_path` instead of `data/`.
- Manual smoke checklist: `python menu_cli.py`, login with sandbox tokens, run menu options 1→5, confirm `data/gtt_plan_cache.json` updates, then exit.

## Operational Tips
- Regenerate Upstox tokens whenever `_fetch_bulk_quote_upstox` logs UDAPI100050; the code already retries but may still require manual confirmation.
- Large CSV writes (tradebook, ROI) can be slow on Windows Defender; pause real-time scanning if menu actions appear frozen while writing.
- Keep `data/gtt_plan_cache.json` small by deleting it after order placement; stale plans confuse EntryPilot and Typer commands alike.
- Clean up auth/data files before zipping or sharing the repo; even anonymized trades can leak strategy information.

## Next Steps
- Keep README.md aligned with any new CLI options or environment variables introduced in the code.
- Expand automated tests when features stabilize so regression coverage grows alongside planner complexity.
- Document manual broker steps (token refresh nods, CSV sourcing) inside `docs/` whenever workflows change.
- The CLI may be deprecated or slimmed down in the future. Ensure AGENTS.md stays aligned with OpenAPI and UI workflows.

## Cursor / Copilot Rules
- No `.cursor/rules` or `.github/copilot-instructions.md` files currently exist; there are no extra editor-agent constraints to follow.
