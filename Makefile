# Beshno — developer task runner.
# Run the database, backend and frontend separately (one per terminal),
# or the whole stack with Docker Compose.

SHELL := /bin/bash

VENV          := backend/.venv
VENV_PY       := $(VENV)/bin/python
BACKEND_PORT  ?= 8000
FRONTEND_PORT ?= 5173

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@echo "Beshno — make targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Typical dev flow (three terminals):"
	@echo "  make db       # PostgreSQL on :5433 (Docker)"
	@echo "  make backend  # FastAPI on :$(BACKEND_PORT)"
	@echo "  make frontend # Vite on :$(FRONTEND_PORT)"

# ---------------------------------------------------------------------------
# Database — PostgreSQL via Docker
# ---------------------------------------------------------------------------
.PHONY: db
db: ## Start PostgreSQL (Docker) on :5433 and wait until it is ready
	docker compose up -d db
	@echo "Waiting for Postgres to become healthy..."
	@for i in $$(seq 1 30); do \
	  status=$$(docker compose ps -q db | xargs -r docker inspect -f '{{.State.Health.Status}}' 2>/dev/null); \
	  if [ "$$status" = "healthy" ]; then \
	    echo "Postgres is ready on localhost:5433 (user/pass/db = beshno)."; exit 0; \
	  fi; \
	  sleep 1; \
	done; \
	echo "Postgres did not become healthy in time. Check 'docker compose logs db'."; exit 1

.PHONY: db-stop
db-stop: ## Stop the PostgreSQL container
	docker compose stop db

.PHONY: db-shell
db-shell: ## Open a psql shell inside the database container
	docker compose exec db psql -U beshno -d beshno

# ---------------------------------------------------------------------------
# Backend — FastAPI
# ---------------------------------------------------------------------------
# Internal: create the venv and install deps. Prefers `uv`, falls back to venv.
$(VENV_PY):
	@if command -v uv >/dev/null 2>&1; then \
	  echo "Creating venv with uv..."; \
	  uv venv $(VENV) && uv pip install --python $(VENV_PY) -r backend/requirements-dev.txt; \
	else \
	  echo "Creating venv with python3 -m venv..."; \
	  python3 -m venv $(VENV) && $(VENV)/bin/pip install -U pip && $(VENV)/bin/pip install -r backend/requirements-dev.txt; \
	fi

.PHONY: backend-install
backend-install: ## (Re)create the backend venv and install dependencies
	rm -rf $(VENV)
	@$(MAKE) $(VENV_PY)

.PHONY: backend
backend: $(VENV_PY) ## Run the backend dev server (http://localhost:8000)
	cd backend && .venv/bin/python -m uvicorn app.main:app --reload --port $(BACKEND_PORT)

.PHONY: test
test: $(VENV_PY) ## Run backend tests (mock providers, SQLite — no keys needed)
	cd backend && .venv/bin/python -m pytest -q

# ---------------------------------------------------------------------------
# Frontend — React + Vite
# ---------------------------------------------------------------------------
frontend/node_modules:
	cd frontend && npm install

.PHONY: frontend-install
frontend-install: ## Install frontend dependencies
	cd frontend && npm install

.PHONY: frontend
frontend: frontend/node_modules ## Run the frontend dev server (http://localhost:5173)
	cd frontend && npm run dev

.PHONY: frontend-build
frontend-build: frontend/node_modules ## Type-check and build the frontend for production
	cd frontend && npm run build

# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------
.PHONY: install
install: backend-install frontend-install ## Install backend + frontend dependencies

.PHONY: up
up: ## Start the entire stack with Docker Compose (db + backend + frontend)
	docker compose up --build

.PHONY: down
down: ## Stop and remove the Docker Compose stack
	docker compose down

.PHONY: clean
clean: ## Remove venv, node_modules, build output and caches
	rm -rf $(VENV) frontend/node_modules frontend/dist
	find backend -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	find backend -type d -name .pytest_cache -prune -exec rm -rf {} + 2>/dev/null || true
