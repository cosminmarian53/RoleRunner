.PHONY: install lint format dev dev-backend dev-frontend test clean

# Install all dependencies + pre-commit hooks
install:
	uv sync --all-extras
	uv run pre-commit install
	cd frontend && npm install

# Run all linters
lint:
	uv run pre-commit run --all-files

# Auto-format code
format:
	uv run black backend/ tests/ scripts/
	uv run isort backend/ tests/ scripts/

# Start both backend and frontend dev servers
dev:
	@echo "Starting backend on :8000 and frontend on :5173..."
	@make dev-backend & make dev-frontend

dev-backend:
	uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

# Run tests
test:
	uv run pytest tests/ -v

# Clean generated files
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf frontend/dist
