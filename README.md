# TradeCraftX

TradeCraftX is a multi-broker trading automation and analysis CLI tool designed for Zerodha and Upstox. It features AI-powered analysis using Google Gemini and Groq to help refine entry strategies, analyze holdings, and manage risk.

## Features

- **Multi-Broker Support**: Seamlessly switch between Zerodha (Kite) and Upstox.
- **AI Analyst**: Integrated with Google Gemini for intelligent market insights and entry level refinement.
- **Holdings Analysis**: Analyze ROI, weighted returns, and filter holdings.
- **GTT Automation**: Analyze variance and automate GTT (Good Till Triggered) orders.
- **Risk Management**: Tools to apply risk management rules to your trading plan.

## Prerequisites

- Python 3.10 or higher
- Accounts with Zerodha or Upstox (with API access enabled)
- API Keys for Google Gemini (and optionally Groq)

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/TradeCraftX.git
   cd TradeCraftX
   ```

2. **Set up the environment:**

   **Windows:**
   Double-click `setup.bat` or run:
   ```cmd
   setup.bat
   ```

   **Mac/Linux:**
   Run the setup script:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

3. **Configure Credentials:**
   - Rename `.env.example` to `.env`.
   - Open `.env` and fill in your API keys for Zerodha, Upstox, and Gemini.

4. **Data Setup:**
   Before running the project, ensure the following data files are in place:
   
   - **`name-symbol-mapping.csv`**: A mapping of stock symbols to their full names.
     ```csv
     Symbol,Name
     RELIANCE,Reliance Industries Ltd
     TCS,Tata Consultancy Services Ltd
     ```
   - **Entry Levels CSV**: A CSV file containing your planned entry levels.
     - **Naming Convention**: `{user_id}-{broker}-entry-levels.csv` (e.g., `NM9100-zerodha-entry-levels.csv`).
     - **Format**: Should contain columns like `Symbol`, `Entry_Level`, `Quantity`.
     ```csv
     Symbol,Entry_Level,Quantity,Note
     RELIANCE,2350,10,Support level
     TCS,3400,5,Long term
     ```
     - *Note*: Ensure the filename matches the User ID you input when running the application.

## Usage

The FastAPI backend powers both CLI and future web UI flows. To run locally:

1. Copy `.env.example` to `.env` and populate all values (broker keys, `JWT_SECRET`, `TOKEN_ENCRYPTION_KEY`, `DEV_MODE`, etc.).
2. Initialize the database schema: `alembic upgrade head`.
3. Start the API: `uvicorn api.main:app --reload` (or `docker compose up`).
4. Health probes:
   - `GET /health` → always 200 if the server process is alive.
   - `GET /ready` → verifies DB access (and, when `HOSTED_MODE=1`, ensures `TOKEN_ENCRYPTION_KEY` exists). Returns 503 otherwise.
5. Authenticate: with `DEV_MODE=1`, a dev tenant/user is auto-provisioned and `/auth/login` will yield a bearer token. In hosted mode, first `POST /auth/register` (admin), then `POST /auth/login`.

### Local Upstox OAuth Smoke Test

1. In the Upstox developer console, register the redirect URI exactly as `http://localhost:8000/brokers/upstox/callback` (or your hosted URL). Any mismatch will cause the login flow to fail.
2. Set `UPSTOX_API_KEY`, `UPSTOX_API_SECRET`, and `UPSTOX_REDIRECT_URI` in `.env` to match the Upstox app configuration.
3. Start the API and obtain a bearer token (`POST /auth/login`).
4. Call `GET /brokers/upstox/connect` with the `Authorization: Bearer <token>` header. The JSON response contains `login_url` and `state`.
5. Open `login_url` in a browser, complete the Upstox consent flow, and the callback page will show `✅ Upstox connected successfully. You may close this tab.`
6. Confirm storage via `GET /brokers/upstox/status` (optionally `?connection_id=...`). When `connected=true`, you can `POST /session/start` with the `broker_connection_id` to run holdings/plan/risk/gtt services without any CLI prompts.

### Local Zerodha OAuth Smoke Test

1.  First, complete the Local Upstox OAuth Smoke Test to ensure an active Upstox connection exists. This is a prerequisite for market data access.
2.  In the Zerodha Kite developer console, register the redirect URI exactly as `http://localhost:8000/brokers/zerodha/callback` (or your hosted URL).
3.  Set `KITE_API_KEY`, `KITE_API_SECRET`, and `KITE_REDIRECT_URI` in `.env`.
4.  Start the API and obtain a bearer token (`POST /auth/login`).
5.  Call `GET /brokers/zerodha/connect` with the `Authorization: Bearer <token>` header. The JSON response contains `authorize_url`.
6.  Open `authorize_url` in a browser, complete the Kite login, and you will be redirected. The callback page will show `✅ Zerodha connected successfully. You may close this tab.`
7.  Confirm storage via `GET /brokers/zerodha/status`. When `connected=true`, you can use this connection for trading operations.

### UI Broker Connections

The React UI Broker Connections page (`/broker-connections`) implements a two-step flow:

- **Upstox First**: When clicking "Connect Zerodha", the UI checks if Upstox is already connected. If not, it prompts to connect Upstox first (market data dependency).
- **Step-by-Step**: A stepper guides users through Upstox → Zerodha connection with polling for connection status (90s timeout).
- **Status Cards**: Both brokers display connection status, user ID, and last token update time.

Connection IDs are stored in localStorage (`tradecraftx_upstox_connection_id`, `tradecraftx_zerodha_connection_id`) for session start.
