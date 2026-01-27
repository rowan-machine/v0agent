.PHONY: help build build-dev run run-dev stop clean test test-unit test-integration test-e2e test-coverage shell logs push pull dev

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
RED := \033[0;31m
NC := \033[0m # No Color

help:
	@echo "$(BLUE)V0Agent Docker & Development Commands$(NC)"
	@echo ""
	@echo "$(GREEN)Local Development:$(NC)"
	@echo "  make dev                Start local dev server (uvicorn with hot reload)"
	@echo "  make test               Run all tests locally"
	@echo "  make test-unit          Run unit tests only"
	@echo "  make test-integration   Run integration tests only"
	@echo "  make test-coverage      Run tests with coverage report"
	@echo ""
	@echo "$(GREEN)Docker Build & Run:$(NC)"
	@echo "  make build              Build production Docker image"
	@echo "  make build-dev          Build development Docker image"
	@echo "  make build-no-cache     Build without Docker cache"
	@echo "  make run                Start all services (app + Redis)"
	@echo "  make run-dev            Start with development image (hot reload)"
	@echo "  make stop               Stop all running containers"
	@echo ""
	@echo "$(GREEN)Testing & Quality:$(NC)"
	@echo "  make test               Run all tests"
	@echo "  make test-unit          Run unit tests only"
	@echo "  make test-integration   Run integration tests only"
	@echo "  make test-e2e           Run end-to-end tests only"
	@echo "  make test-coverage      Run tests with coverage report"
	@echo "  make lint               Run linters (black, isort, pylint)"
	@echo "  make format             Format code (black, isort)"
	@echo ""
	@echo "$(GREEN)Maintenance:$(NC)"
	@echo "  make shell              Open bash shell in running app container"
	@echo "  make logs               Tail app logs"
	@echo "  make logs-redis         Tail Redis logs"
	@echo "  make clean              Stop containers and remove volumes"
	@echo "  make clean-all          Clean + remove images"
	@echo ""
	@echo "$(GREEN)Registry (Docker Hub):$(NC)"
	@echo "  make push               Push image to registry"
	@echo "  make pull               Pull image from registry"
	@echo ""
	@echo "$(GREEN)Advanced:$(NC)"
	@echo "  make docker-info        Show Docker system info"
	@echo "  make prune              Remove unused Docker resources"

# ===== Build Targets =====
build:
	@echo "$(BLUE)Building production Docker image...$(NC)"
	docker build -t v0agent:latest \
		--target runtime \
		-f Dockerfile .
	@echo "$(GREEN)✓ Build complete: v0agent:latest$(NC)"

build-dev:
	@echo "$(BLUE)Building development Docker image...$(NC)"
	docker build -t v0agent:dev \
		--target development \
		-f Dockerfile .
	@echo "$(GREEN)✓ Build complete: v0agent:dev$(NC)"

build-no-cache:
	@echo "$(BLUE)Building production image without cache...$(NC)"
	docker build -t v0agent:latest \
		--target runtime \
		--no-cache \
		-f Dockerfile .
	@echo "$(GREEN)✓ Build complete: v0agent:latest (no cache)$(NC)"

# ===== Run Targets =====
run:
	@echo "$(BLUE)Starting services (production with Redis)...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)✓ Services started$(NC)"
	@echo "$(BLUE)App: http://localhost:8000$(NC)"
	@echo "$(BLUE)Redis: localhost:6379$(NC)"

run-dev:
	@echo "$(BLUE)Starting services (development with hot reload)...$(NC)"
	docker-compose -f docker-compose.yaml up
	@echo "$(GREEN)✓ Development server started (hot reload enabled)$(NC)"

# ===== Local Development =====
dev:
	@echo "$(BLUE)Starting local dev server...$(NC)"
	uvicorn src.app.main:app --reload --port 8001

logs-redis:
	@echo "$(BLUE)Tailing Redis logs (Ctrl+C to exit)...$(NC)"
	docker-compose logs -f redis

stop:
	@echo "$(BLUE)Stopping all services...$(NC)"
	docker-compose down
	@echo "$(GREEN)✓ Services stopped$(NC)"

# ===== Testing Targets =====
test:
	@echo "$(BLUE)Running all tests...$(NC)"
	pytest tests/ -v
	@echo "$(GREEN)✓ Tests complete$(NC)"

test-unit:
	@echo "$(BLUE)Running unit tests...$(NC)"
	pytest tests/unit -v
	@echo "$(GREEN)✓ Unit tests complete$(NC)"

test-integration:
	@echo "$(BLUE)Running integration tests...$(NC)"
	pytest tests/integration -v
	@echo "$(GREEN)✓ Integration tests complete$(NC)"

test-e2e:
	@echo "$(BLUE)Running E2E tests...$(NC)"
	pytest tests/e2e -v
	@echo "$(GREEN)✓ E2E tests complete$(NC)"

test-smoke:
	@echo "$(BLUE)Running smoke tests...$(NC)"
	pytest tests/smoke -v
	@echo "$(GREEN)✓ Smoke tests complete$(NC)"

test-coverage:
	@echo "$(BLUE)Running tests with coverage...$(NC)"
	pytest tests/ \
		--cov=src/app \
		--cov-report=html \
		--cov-report=term-missing
	@echo "$(GREEN)✓ Coverage report generated$(NC)"
	@echo "$(BLUE)Open htmlcov/index.html to view detailed report$(NC)"

# ===== Docker Testing (if needed) =====
test-docker:
	@echo "$(BLUE)Running all tests in Docker...$(NC)"
	docker-compose exec -T app pytest tests/ -v
	@echo "$(GREEN)✓ Docker tests complete$(NC)"

# ===== Quality Targets =====
lint:
	@echo "$(BLUE)Running linters...$(NC)"
	docker-compose exec -T app pylint src/
	docker-compose exec -T app flake8 src/
	@echo "$(GREEN)✓ Linting complete$(NC)"

format:
	@echo "$(BLUE)Formatting code...$(NC)"
	docker-compose exec -T app black src/ tests/
	docker-compose exec -T app isort src/ tests/
	@echo "$(GREEN)✓ Formatting complete$(NC)"

security:
	@echo "$(BLUE)Running security checks...$(NC)"
	docker-compose exec -T app bandit -r src/ -ll
	@echo "$(GREEN)✓ Security scan complete$(NC)"

# ===== Maintenance Targets =====
shell:
	@echo "$(BLUE)Opening shell in app container...$(NC)"
	docker-compose exec app /bin/bash

logs:
	@echo "$(BLUE)Tailing app logs (Ctrl+C to exit)...$(NC)"
	docker-compose logs -f app

logs-redis:
	@echo "$(BLUE)Tailing Redis logs (Ctrl+C to exit)...$(NC)"
	docker-compose logs -f redis

clean:
	@echo "$(BLUE)Stopping containers and removing volumes...$(NC)"
	docker-compose down -v
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

clean-all: clean
	@echo "$(BLUE)Removing Docker images...$(NC)"
	docker rmi v0agent:latest v0agent:dev 2>/dev/null || true
	@echo "$(GREEN)✓ Full cleanup complete$(NC)"

docker-info:
	@echo "$(BLUE)Docker System Information$(NC)"
	docker system df
	@echo ""
	@echo "$(BLUE)Running Containers$(NC)"
	docker ps
	@echo ""
	@echo "$(BLUE)All Containers$(NC)"
	docker ps -a

prune:
	@echo "$(BLUE)Pruning unused Docker resources...$(NC)"
	docker system prune -f
	@echo "$(GREEN)✓ Prune complete$(NC)"

# ===== Registry Targets =====
push:
	@echo "$(BLUE)Tagging and pushing to registry...$(NC)"
	docker tag v0agent:latest myregistry.azurecr.io/v0agent:latest
	docker push myregistry.azurecr.io/v0agent:latest
	@echo "$(GREEN)✓ Push complete$(NC)"

pull:
	@echo "$(BLUE)Pulling from registry...$(NC)"
	docker pull myregistry.azurecr.io/v0agent:latest
	docker tag myregistry.azurecr.io/v0agent:latest v0agent:latest
	@echo "$(GREEN)✓ Pull complete$(NC)"

# ===== Development Quick Commands =====
.PHONY: quick-start quick-stop quick-logs quick-shell

quick-start: build run
	@echo "$(GREEN)✓ Quick start complete!$(NC)"

quick-stop: stop

quick-logs: logs

quick-shell: shell

# Default target
.DEFAULT_GOAL := help
