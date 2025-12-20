.PHONY: help build test clean docker-build docker-run docker-worker docker-manualfetch docker-migrate-up docker-migrate-down fmt lint vet mod

# ==============================================================================
# NCAAF v5.0 Ingestion Service Makefile
# ==============================================================================
# IMPORTANT: All runtime operations MUST go through Docker containers.
# This Makefile provides:
#   - Build/test commands (for CI/development)
#   - Docker-based commands (for running services)
#
# DO NOT run services locally - use docker-* targets instead.
# ==============================================================================

# Variables
APP_NAME=ncaaf-ingestion
DOCKER_IMAGE=ncaaf-v5/ingestion
COMPOSE_FILE=../docker-compose.yml
GO_FILES=$(shell find . -name '*.go' -type f)

help: ## Show this help message
	@echo "NCAAF v5.0 Ingestion Service"
	@echo "=============================="
	@echo ""
	@echo "⚠️  All runtime operations must use Docker (docker-* targets)"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Build & Test (CI/Development):"
	@grep -E '^(build|test|fmt|lint|vet|mod|clean):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'
	@echo ""
	@echo "Docker Operations (Runtime - REQUIRED):"
	@grep -E '^docker-.*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'
	@echo ""
	@echo "Examples:"
	@echo "  make docker-worker        # Start worker in Docker"
	@echo "  make docker-manualfetch   # Run manual fetch in Docker"
	@echo "  make docker-migrate-up    # Run migrations in Docker"

# ==============================================================================
# BUILD & TEST (for CI/Development only)
# ==============================================================================

build: ## Build Go binaries (for Docker image build)
	@echo "Building $(APP_NAME) binaries..."
	@CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o bin/worker ./cmd/worker
	@CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o bin/manualfetch ./cmd/manualfetch
	@echo "Build complete: bin/worker, bin/manualfetch"

test: ## Run tests (for CI)
	@echo "Running tests..."
	@go test -v -race -coverprofile=coverage.out ./...
	@go tool cover -html=coverage.out -o coverage.html
	@echo "Coverage report: coverage.html"

test-short: ## Run short tests (no integration tests)
	@go test -v -short ./...

test-integration: ## Run integration tests in Docker
	@echo "Running integration tests via Docker..."
	@docker compose -f $(COMPOSE_FILE) run --rm ingestion go test -v -tags=integration ./internal/repository/...

fmt: ## Format Go code
	@echo "Formatting code..."
	@go fmt ./...
	@gofmt -s -w .

lint: ## Lint Go code
	@echo "Linting code..."
	@golangci-lint run ./...

vet: ## Run go vet
	@go vet ./...

mod: ## Download and tidy Go modules
	@echo "Downloading modules..."
	@go mod download
	@go mod tidy

clean: ## Clean build artifacts
	@echo "Cleaning..."
	@rm -rf bin/
	@rm -f coverage.out coverage.html
	@echo "Clean complete"

# ==============================================================================
# DOCKER OPERATIONS (REQUIRED for all runtime operations)
# ==============================================================================

docker-build: ## Build Docker image
	@echo "Building Docker image..."
	@docker build -t $(DOCKER_IMAGE):latest .

docker-run: ## Run Docker container (interactive)
	@echo "Running Docker container..."
	@docker compose -f $(COMPOSE_FILE) run --rm ingestion

docker-worker: ## Start ingestion worker via Docker (RECOMMENDED)
	@echo "Starting ingestion worker via Docker..."
	@docker compose -f $(COMPOSE_FILE) up -d ingestion
	@echo "Worker started. View logs: docker compose logs -f ingestion"

docker-manualfetch: ## Run manual fetch via Docker (RECOMMENDED)
	@echo "Running manualfetch via Docker..."
	@docker compose -f $(COMPOSE_FILE) -f ../docker-compose.manualfetch.yml run --rm ingestion

docker-migrate-up: ## Run database migrations via Docker (RECOMMENDED)
	@echo "Running migrations via Docker..."
	@docker compose -f $(COMPOSE_FILE) run --rm ingestion sh -c "migrate -path /app/migrations -database \$$DATABASE_URL up"

docker-migrate-down: ## Rollback database migrations via Docker
	@echo "Rolling back migrations via Docker..."
	@docker compose -f $(COMPOSE_FILE) run --rm ingestion sh -c "migrate -path /app/migrations -database \$$DATABASE_URL down 1"

docker-logs: ## View ingestion service logs
	@docker compose -f $(COMPOSE_FILE) logs -f ingestion

docker-shell: ## Open shell in ingestion container
	@docker compose -f $(COMPOSE_FILE) run --rm ingestion sh

# ==============================================================================
# DEPRECATED - DO NOT USE
# ==============================================================================
# The following targets are deprecated and will be removed.
# Use docker-* equivalents instead.

run: ## DEPRECATED: Use 'make docker-worker' instead
	@echo "⚠️  DEPRECATED: Local execution is not supported."
	@echo "Use: make docker-worker"
	@exit 1

run-webhook: ## DEPRECATED: Use 'make docker-run' instead
	@echo "⚠️  DEPRECATED: Local execution is not supported."
	@echo "Use: make docker-run"
	@exit 1

manualfetch: ## DEPRECATED: Use 'make docker-manualfetch' instead
	@echo "⚠️  DEPRECATED: Local execution is not supported."
	@echo "Use: make docker-manualfetch"
	@exit 1

migrate-up: ## DEPRECATED: Use 'make docker-migrate-up' instead
	@echo "⚠️  DEPRECATED: Local execution is not supported."
	@echo "Use: make docker-migrate-up"
	@exit 1

migrate-down: ## DEPRECATED: Use 'make docker-migrate-down' instead
	@echo "⚠️  DEPRECATED: Local execution is not supported."
	@echo "Use: make docker-migrate-down"
	@exit 1

seed: ## DEPRECATED: Use Docker-based seeding
	@echo "⚠️  DEPRECATED: Local execution is not supported."
	@echo "Use: docker compose run --rm ingestion /app/bin/seed"
	@exit 1

.DEFAULT_GOAL := help
