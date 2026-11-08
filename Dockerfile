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

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency specifications and install
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -e .

# Create persistent data directory and copy initial pre-seeded database
RUN mkdir -p /app/data
COPY plm_mock.db /app/data/plm_mock.db

# Copy all root Python modules (including validators.py, windchill_mapper.py, seed_data.py)
COPY *.py ./
COPY *.sql ./
COPY src/ ./src/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]
