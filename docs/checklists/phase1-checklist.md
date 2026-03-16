# Phase 1 Production Hardening Checklist

## Objective
Incrementally harden the application for production deployment without changing runtime behavior.

## Steps

### 1. Health & Monitoring Endpoints
- [ ] `/health` endpoint returns status, time, version
- [ ] `/ready` endpoint checks DB connectivity
- [ ] No authentication required on health endpoints
- [ ] Health endpoint tested locally

### 2. Request Tracing
- [ ] Request ID middleware added
- [ ] `X-Request-ID` header returned in all responses
- [ ] Request ID included in application logs
- [ ] Logs show request_id for API calls

### 3. Documentation
- [ ] Local production smoke test steps documented
- [ ] Phase checklist created and updated

### 4. Verification Commands

```bash
# Test health endpoint
curl http://localhost:8000/health

# Test with request ID header
curl -v http://localhost:8000/health 2>&1 | grep -i "X-Request-ID"

# Start in prod mode
APP_MODE=prod python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

## Notes
- Do NOT modify authentication flows
- Do NOT change broker connection logic
- Do NOT alter DB schema
