# Build stage: Node.js to build React frontend
FROM node:18-alpine AS frontend

# Set working directory
WORKDIR /app/ui

# Copy package files
COPY ui/package.json ui/package-lock.json* ./

# Install dependencies
RUN npm ci

# Copy source
COPY ui/ .

# Build the frontend
RUN npm run build

# Production stage: Python to run FastAPI
FROM python:3.11-slim AS backend

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy alembic configuration
COPY alembic.ini .
COPY alembic ./alembic

# Copy API code
COPY api ./api
COPY db ./db
COPY core ./core
COPY brokers ./brokers
COPY agent ./agent

# Create data directory
RUN mkdir -p /app/data

# Copy built frontend from build stage to the app root
COPY --from=frontend /app/ui/dist /app/ui/dist

# Expose port
EXPOSE 8000

# Run database migrations and start the server
CMD sh -c "python -m alembic upgrade head && uvicorn api.main:app --host 0.0.0.0 --port $PORT"
