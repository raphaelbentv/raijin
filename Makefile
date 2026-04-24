.DEFAULT_GOAL := help
SHELL := /bin/bash

COMPOSE := docker compose

## ─── Stack lifecycle ─────────────────────────────────────────

.PHONY: up
up: ## Start the full stack
	$(COMPOSE) up -d --build

.PHONY: down
down: ## Stop the stack
	$(COMPOSE) down

.PHONY: down-volumes
down-volumes: ## Stop and wipe volumes (destructive)
	$(COMPOSE) down -v

.PHONY: restart
restart: down up

.PHONY: ps
ps: ## Show running services
	$(COMPOSE) ps

## ─── Logs ────────────────────────────────────────────────────

.PHONY: logs
logs: ## Tail logs from all services
	$(COMPOSE) logs -f --tail=100

.PHONY: logs-backend
logs-backend:
	$(COMPOSE) logs -f --tail=100 backend

.PHONY: logs-worker
logs-worker:
	$(COMPOSE) logs -f --tail=100 worker

.PHONY: logs-frontend
logs-frontend:
	$(COMPOSE) logs -f --tail=100 frontend

## ─── Database ────────────────────────────────────────────────

.PHONY: migrate
migrate: ## Apply all pending Alembic migrations
	$(COMPOSE) exec backend alembic upgrade head

.PHONY: migration
migration: ## Create a new migration. Usage: make migration m="add users table"
	@if [ -z "$(m)" ]; then echo "Usage: make migration m=\"message\""; exit 1; fi
	$(COMPOSE) exec backend alembic revision --autogenerate -m "$(m)"

.PHONY: downgrade
downgrade: ## Rollback one migration
	$(COMPOSE) exec backend alembic downgrade -1

.PHONY: psql
psql: ## Open psql shell
	$(COMPOSE) exec postgres psql -U raijin -d raijin

## ─── Quality ─────────────────────────────────────────────────

.PHONY: test
test: ## Run full test suite
	$(COMPOSE) exec backend pytest
	$(COMPOSE) exec worker pytest
	$(COMPOSE) exec frontend npm test

.PHONY: test-backend
test-backend:
	$(COMPOSE) exec backend pytest

.PHONY: lint
lint: ## Run linters
	$(COMPOSE) exec backend ruff check .
	$(COMPOSE) exec worker ruff check .
	$(COMPOSE) exec frontend npm run lint

.PHONY: format
format: ## Auto-format code
	$(COMPOSE) exec backend ruff format .
	$(COMPOSE) exec worker ruff format .
	$(COMPOSE) exec frontend npm run format

## ─── Shells ──────────────────────────────────────────────────

.PHONY: shell-backend
shell-backend:
	$(COMPOSE) exec backend bash

.PHONY: shell-worker
shell-worker:
	$(COMPOSE) exec worker bash

.PHONY: shell-frontend
shell-frontend:
	$(COMPOSE) exec frontend sh

## ─── Help ────────────────────────────────────────────────────

.PHONY: help
help:
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
