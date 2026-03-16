# Render Deployment Guide

This guide covers deploying TradeCraftX to Render.com with ephemeral SQLite.

## Prerequisites

- GitHub repository with TradeCraftX code
- Render.com account

## Step 1: Create Web Service

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Configure the service:
   - **Name**: `tradecraftx`
   - **Environment**: `Python`
   - **Build Command**: (empty - using Dockerfile)
   - **Start Command**: (empty - using Dockerfile)
   - **Plan**: Free or Starded

## Step 2: Configure Environment Variables

Add these environment variables in Render dashboard:

| Variable | Value | Description |
|----------|-------|-------------|
| `APP_MODE` | `prod` | Run in production mode |
| `DATABASE_URL` | `sqlite:////app/data/tradecraftx.db` | Ephemeral SQLite path |
| `JWT_SECRET` | `<generate-random-32-chars>` | Production JWT secret (min 32 chars) |
| `TOKEN_ENCRYPTION_KEY` | `<generate-base64-32-byte-key>` | Encryption key for tokens |

### Generating Secrets

```bash
# Generate JWT_SECRET (32+ characters)
openssl rand -base64 32

# Generate TOKEN_ENCRYPTION_KEY (32 bytes, base64url encoded)
openssl rand -base64 32
```

## Step 3: Configure Render YAML (Optional)

Create `render.yaml` in repository root:

```yaml
services:
  - type: web
    name: tradecraftx
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: sh -c "python -m alembic upgrade head && uvicorn api.main:app --host 0.0.0.0 --port $PORT"
    envVars:
      - key: APP_MODE
        value: prod
      - key: DATABASE_URL
        value: sqlite:////app/data/tradecraftx.db
      - key: JWT_SECRET
        generateValue: true
      - key: TOKEN_ENCRYPTION_KEY
        generateValue: true
    disk:
      name: tradecraftx-data
      mountPath: /app/data
      sizeGB: 1
```

## Step 4: Database Disk

For SQLite persistence across deploys:

1. In Render dashboard, go to your web service
2. Click "Disks" → "Add Disk"
3. Configure:
   - **Name**: `tradecraftx-data`
   - **Mount Path**: `/app/data`
   - **Size**: 1GB

## Step 5: Deploy

1. Click "Create Web Service" or trigger deploy
2. Watch build logs for:
   - Python dependencies installation
   - Database migrations (`python -m alembic upgrade head`)
   - Server startup

## Important Notes

### Ephemeral Filesystem
- SQLite database is stored in `/app/data/`
- Without a disk, data is lost on each deploy
- With a disk, data persists across deploys

### First Deploy
- Migrations run automatically on first deploy
- Check logs for "Running upgrade" messages

### Troubleshooting

#### Migration Failed
- Check DATABASE_URL is correct
- Ensure disk is mounted at /app/data

#### 500 Error on Startup
- Check JWT_SECRET is set (required in prod mode)
- Check TOKEN_ENCRYPTION_KEY is set

#### CORS Errors
- In prod mode, configure allowed origins in config

## Verify Deployment

```bash
# Health check
curl https://your-service.onrender.com/health

# Expected: {"status":"ok",...}

# Login
curl -X POST https://your-service.onrender.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@tradecraft.com","password":"<password>"}'
```

## Security Checklist

- [ ] JWT_SECRET is long (32+ chars)
- [ ] TOKEN_ENCRYPTION_KEY is set
- [ ] APP_MODE=prod
- [ ] DEV_MODE not set (backward compat override)
- [ ] Allowed origins configured for CORS
