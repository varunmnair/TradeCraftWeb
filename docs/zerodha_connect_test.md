# Zerodha Integration Testing Runbook

## Prerequisites
- API running at `http://localhost:8000`
- Valid Upstox and Zerodha API keys in `.env`

## Curl Sequence

### 1. Authenticate
```bash
# Register (first time only)
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"tenant_name":"test","email":"test@example.com","password":"test123"}'

# Login to get JWT
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123"}'
# Returns: {"access_token":"eyJ..."}
export TOKEN="eyJ..."
```

### 2. Connect Upstox
```bash
# Get authorize URL
curl -X GET "http://localhost:8000/brokers/upstox/connect" \
  -H "Authorization: Bearer $TOKEN"
# Returns: {"authorize_url":"https://api.upstox.com/...","state":"...","connection_id":1}

# Open authorize_url in browser, complete login
# Then poll for status
curl -X GET "http://localhost:8000/brokers/upstox/status?connection_id=1" \
  -H "Authorization: Bearer $TOKEN"
# Returns: {"connections":[{"connection_id":1,"connected":true,"broker_user_id":"..."}]}
export UPSTOX_CONN_ID=1
```

### 3. Connect Zerodha (requires Upstox)
```bash
# Try to connect Zerodha without Upstox - should fail with 409
curl -X GET "http://localhost:8000/brokers/zerodha/connect" \
  -H "Authorization: Bearer $TOKEN"
# Returns 409: {"error_code":"upstox_required","message":"Upstox connection required...","context":{"required_broker":"upstox"},"retryable":true}

# With Upstox connected, get authorize URL
curl -X GET "http://localhost:8000/brokers/zerodha/connect" \
  -H "Authorization: Bearer $TOKEN"
# Returns: {"authorize_url":"https://kite.zerodha.com/connect/login?v=3&...","state":"...","connection_id":2}

# Open authorize_url in browser, complete login
# Callback automatically redirects to /brokers/zerodha/callback?request_token=...&state=...

# Then poll for status
curl -X GET "http://localhost:8000/brokers/zerodha/status?connection_id=2" \
  -H "Authorization: Bearer $TOKEN"
# Returns: {"connections":[{"connection_id":2,"connected":true,"broker_user_id":"...","token_updated_at":"..."}]}
export ZERODHA_CONN_ID=2
```

### 3b. Callback Error Cases
```bash
# Invalid state token
curl -X GET "http://localhost:8000/brokers/zerodha/callback?request_token=abc&state=invalid" \
  -H "Authorization: Bearer $TOKEN"
# Returns HTML error page: "Authorization failed: ..."
```

### 4. Start Session (Zerodha)
```bash
# Start session with Zerodha trading + Upstox market data
curl -X POST http://localhost:8000/session/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"broker_connection_id\":$ZERODHA_CONN_ID,\"broker_name\":\"zerodha\",\"market_data_connection_id\":$UPSTOX_CONN_ID}"
# Returns: {"session_id":"...","user_id":"...","broker":"zerodha","expires_at":"..."}
export SESSION_ID="..."
```

### 5. Run Holdings Analyze
```bash
# Queue analyze job
curl -X POST http://localhost:8000/holdings/analyze \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION_ID\"}"
# Returns: {"job_id":123}

# Poll job status
curl -X GET "http://localhost:8000/jobs/123" \
  -H "Authorization: Bearer $TOKEN"
# Returns: {"job":{"id":123,"status":"completed","progress":100}}

# Get holdings
curl -X GET "http://localhost:8000/holdings/$SESSION_ID/latest" \
  -H "Authorization: Bearer $TOKEN"
```

### 6. Plan/GTT Smoke
```bash
# Generate plan
curl -X POST http://localhost:8000/plan/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION_ID\"}"
# Returns: {"job_id":124}

# Preview GTT
curl -X POST http://localhost:8000/gtt/preview \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION_ID\",\"plan\":[]}"
```

## UI Steps

1. **Navigate to** `http://localhost:5173/broker-connections`

2. **Connect Upstox**
   - Click "Connect Upstox"
   - Complete login in popup
   - Verify "Connected" status chip

3. **Connect Zerodha**
   - Click "Connect Zerodha"
   - If Upstox not connected: dialog prompts to connect Upstox first
   - If Upstox connected: opens Zerodha login directly
   - Complete login
   - Verify "Connected" status

4. **Start Session**
   - Go to `http://localhost:5173/sessions`
   - Select Zerodha connection from dropdown
   - Click "Start Session"
   - Verify active session shows "broker: zerodha"

5. **Smoke Tests**
   - Holdings: Go to `/holdings`, verify positions load
   - Plan: Go to `/plan`, generate plan
   - GTT: Go to `/gtt`, preview orders
