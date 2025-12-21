# NextDNS Blocker - Development Makefile
#
# Docker-based development commands for consistent dev environment

.PHONY: help dev shell test test-fast lint typecheck format build clean

# Default target
help:
	@echo "NextDNS Blocker - Development Commands"
	@echo ""
	@echo "Docker Development:"
	@echo "  make dev        - Open interactive dev shell in container"
	@echo "  make shell      - Alias for 'make dev'"
	@echo "  make test       - Run full test suite with coverage"
	@echo "  make test-fast  - Run tests without coverage (faster)"
	@echo "  make lint       - Run ruff linter"
	@echo "  make typecheck  - Run mypy type checker"
	@echo ""
	@echo "Local Development:"
	@echo "  make format     - Format code with ruff and black (local)"
	@echo "  make build      - Build production Docker image"
	@echo "  make clean      - Remove Docker dev artifacts"
	@echo ""

# Docker compose command shortcut
COMPOSE_DEV = docker compose -f docker-compose.dev.yml

# Open interactive dev shell
dev:
	$(COMPOSE_DEV) run --rm dev

# Alias for dev
shell: dev

# Run full test suite with coverage
test:
	$(COMPOSE_DEV) run --rm test

# Run tests without coverage (faster iteration)
test-fast:
	$(COMPOSE_DEV) run --rm dev pytest tests/ -v

# Run ruff linter
lint:
	$(COMPOSE_DEV) run --rm lint

# Run mypy type checker
typecheck:
	$(COMPOSE_DEV) run --rm typecheck

# Format code (runs locally, not in container)
format:
	@echo "Formatting code with ruff and black..."
	ruff check --fix src/ tests/
	black src/ tests/

# Build production Docker image
build:
	docker build -t nextdns-blocker:latest .

# Clean up Docker dev artifacts
clean:
	$(COMPOSE_DEV) down --rmi local --volumes --remove-orphans
	@echo "Cleaned up Docker dev artifacts"
