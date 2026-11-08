# ThreadMind Backend Production Dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    PLM_BACKEND=mock \
    PLM_SQLITE_PATH=/app/data/plm_mock.db \
    PLM_SEED_ON_STARTUP=true \
    CORS_ALLOW_ALL=false

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

# Copy backend application source
COPY api.py api_schemas.py chat_service.py config.py \
     plm_interface.py mock_backend.py windchill_backend.py \
     erp_interface.py mock_erp_backend.py \
     qms_interface.py mock_qms_backend.py \
     iiot_interface.py mock_iiot_backend.py \
     telemetry.py server.py ./
COPY src/ ./src/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]

