# ThreadMind Backend Production Dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    PLM_BACKEND=mock \
    PLM_SQLITE_PATH=/app/data/plm_mock.db \
    PLM_SEED_ON_STARTUP=true \
    CORS_ALLOW_ALL=true \
    PYTHONPATH=/app:/app/src

WORKDIR /app

# Install system dependencies (curl for healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 1. Install base dependencies from requirements.txt
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 2. Copy package definitions and install local package
COPY README.md pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e . || true

# 3. Create persistent data directory and copy pre-seeded database
RUN mkdir -p /app/data
COPY plm_mock.db /app/data/plm_mock.db

# 4. Copy all root Python modules and SQL schemas
COPY *.py ./
COPY *.sql ./

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]
