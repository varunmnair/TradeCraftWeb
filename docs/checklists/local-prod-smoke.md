# Local Production Smoke Tests

## Prerequisites
- `.env` file configured (copy from `.env.example`)
- All dependencies installed (`pip install -r requirements.txt`)
- Database initialized

## Start API in Production Mode

### Option 1: Using environment variable
```bash
# Set production mode
set APP_MODE=prod

# Start server
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Option 2: Using .env file
Add to your `.env`:
```
APP_MODE=prod
JWT_SECRET=your-production-secret-min-32-chars
TOKEN_ENCRYPTION_KEY=base64url_32byte_key_for_prod
```

### Option 3: Using docker-compose
```bash
docker-compose up --build
```

## Smoke Test Steps

### 1. Health Endpoints

```bash
# Basic health check (no auth required)
curl http://localhost:8000/health
# Expected: {"status":"ok","time":"2026-03-16T12:00:00Z","version":"0.2.0"}

# Readiness check (includes DB check)
curl http://localhost:8000/ready
# Expected: {"status":"ready"} (or 503 if DB unavailable)
```

### 2. Request ID Header

```bash
# Verify X-Request-ID is returned
curl -v http://localhost:8000/health 2>&1 | findstr "X-Request-ID"
# Expected: X-Request-ID: <uuid>

# Verify request_id appears in logs
# Check console output for request_id in logs
```

### 3. Authentication

```bash
# Register a new user (if not using dev user)
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"tenant_name":"TestCo","email":"test@example.com","password":"testpass123"}'

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123"}'
# Expected: Returns access_token
```

### 4. Broker Connection Flow (Optional - Requires Real API Keys)

```bash
# Get Upstox auth URL (requires login first)
curl -X GET "http://localhost:8000/brokers/upstox/connect" \
  -H "Authorization: Bearer <access_token>"
```

### 5. Entry Strategies (Requires Active Broker Connection)

```bash
# Set active broker connection
curl -X POST "http://localhost:8000/session/active-connection" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"broker_connection_id": 1}'

# List entry strategies (no session_id required in prod mode)
curl -X GET "http://localhost:8000/entry-strategies" \
  -H "Authorization: Bearer <access_token>"
```

## Verification Checklist

- [ ] `/health` returns 200 with JSON
- [ ] `/ready` returns 200 (when DB is available)
- [ ] `X-Request-ID` header present in responses
- [ ] Request IDs appear in server logs
- [ ] Authentication flow works
- [ ] No authentication bypasses in non-dev mode
- [ ] Trading disabled by default (trading_enabled=false for new users)

## Troubleshooting

### DB Connection Failed
- Check database path exists
- Verify `DATABASE_URL` in `.env`

### Token Encryption Error
- Set `TOKEN_ENCRYPTION_KEY` in `.env` for production
- Ensure it's a valid base64url encoded 32-byte key

### JWT Secret Error
- Set `JWT_SECRET` in `.env` for production (minimum 32 characters)

### CORS Errors
- Verify `allow_origins` in CORSMiddleware configuration
