.PHONY: help install lint format typecheck check dev dev-backend dev-frontend dev-worker test test-cov test-fast db-migrate db-upgrade db-downgrade mcp-server build clean

# Default target
help:
	@echo "========================================================================"
	@echo " Job-Bot Development Commands"
	@echo "========================================================================"
	@echo "  make install        Install backend & frontend dependencies + git hooks"
	@echo "  make check          Run linters, type checks, and tests"
	@echo "  make lint           Run all pre-commit linters on all files"
	@echo "  make format         Auto-format Python code (Black & isort)"
	@echo "  make typecheck      Run Mypy static type analysis"
	@echo "  make test           Run all pytest test suites"
	@echo "  make test-cov       Run tests with terminal coverage summary"
	@echo "  make test-fast      Run tests in quick mode without verbose logs"
	@echo "  make dev            Start backend (:8000) and frontend (:5173) in parallel"
	@echo "  make dev-backend    Start FastAPI backend development server"
	@echo "  make dev-frontend   Start Vite React development server"
	@echo "  make dev-worker     Start ARQ background worker"
	@echo "  make db-migrate m=\"msg\" Generate a new Alembic migration"
	@echo "  make db-upgrade     Apply all pending database migrations"
	@echo "  make db-downgrade   Roll back the last database migration"
	@echo "  make mcp-server     Start the stdio Python MCP server"
	@echo "  make build          Build frontend production bundle"
	@echo "  make clean          Remove caches, temp files, and build artifacts"
	@echo "========================================================================"

# Install dependencies and hooks
install:
	uv sync --all-extras
	uv run pre-commit install
	cd frontend && npm install

# Formatting and linting
lint:
	uv run pre-commit run --all-files

format:
	uv run black backend/ tests/ scripts/
	uv run isort backend/ tests/ scripts/

typecheck:
	uv run mypy backend/ tests/ scripts/

check: lint typecheck test

# Development servers
dev:
	@echo "Starting backend on :8000 and frontend on :5173..."
	@make dev-backend & make dev-frontend

dev-backend:
	uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

dev-worker:
	uv run arq backend.workers.worker.WorkerSettings

# Testing
test:
	uv run pytest tests/ -v

test-fast:
	uv run pytest tests/ -q

test-cov:
	uv run pytest tests/ -v --cov=backend --cov-report=term-missing

# Database & Alembic migrations
db-migrate:
	@if [ -z "$(m)" ]; then echo "Usage: make db-migrate m=\"migration description\""; exit 1; fi
	uv run alembic revision --autogenerate -m "$(m)"

db-upgrade:
	uv run alembic upgrade head

db-downgrade:
	uv run alembic downgrade -1

# MCP Server
mcp-server:
	uv run python -m backend.mcp.server

# Production Build
build:
	cd frontend && npm run build

# Clean generated caches and artifacts
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf frontend/dist
