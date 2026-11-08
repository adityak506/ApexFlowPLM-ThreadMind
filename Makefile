# Makefile for ThreadMind Mock PLM System & Observability Stack

.PHONY: help obs-up obs-down obs-ps obs-logs api ui test

help:
	@echo "ThreadMind PLM Commands:"
	@echo "  make obs-up    - Start OpenTelemetry, Prometheus, Tempo, Loki, and Grafana"
	@echo "  make obs-down  - Stop all observability containers"
	@echo "  make obs-ps    - View status of observability containers"
	@echo "  make obs-logs  - Follow container logs"
	@echo "  make api       - Start FastAPI backend with OTel auto-instrumentation"
	@echo "  make ui        - Start Vite React UI on http://localhost:5173"
	@echo "  make test      - Run all pytest automated test suites"

obs-up:
	docker compose -f observability/docker-compose.yml up -d

obs-down:
	docker compose -f observability/docker-compose.yml down

obs-ps:
	docker compose -f observability/docker-compose.yml ps

obs-logs:
	docker compose -f observability/docker-compose.yml logs -f

api:
	python -m uvicorn api:app --host 127.0.0.1 --port 8000

ui:
	npm --prefix ui run dev

test:
	python -m pytest tests/
