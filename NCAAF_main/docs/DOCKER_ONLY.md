# Docker-Only Execution Policy

## Single Source of Truth

**All runtime operations in NCAAF v5.0 MUST run through Docker containers.**

This policy ensures:
- ✅ **Consistent environments** across development, CI/CD, and production
- ✅ **Reproducible results** - same container, same behavior
- ✅ **No "works on my machine"** issues
- ✅ **Simplified debugging** - one environment to troubleshoot
- ✅ **Security isolation** - services run in controlled containers

---

## Allowed Operations

### ✅ Development & CI (Build/Test Only)

These operations run on the host for speed during development:

| Operation | Location | Purpose |
|-----------|----------|---------|
| `go build` | Host | Compile binaries (for Docker image) |
| `go test -short` | Host | Unit tests (CI only) |
| `go fmt`, `go vet` | Host | Code formatting/linting |
| `pip install` | Host | Install dev tools (CI only) |
| `pytest` (unit tests) | Host | Unit tests (CI only) |

### ✅ Runtime Operations (Docker REQUIRED)

All actual execution must use Docker:

| Operation | Command | Docker |
|-----------|---------|--------|
| Start services | `docker compose up -d` | ✅ Required |
| Run predictions | `run.bat predict` or `docker compose run --rm ml_service python main.py predict` | ✅ Required |
| Train models | `run.bat train` or `docker compose run --rm ml_service python main.py train` | ✅ Required |
| Manual fetch | `docker compose -f docker-compose.yml -f docker-compose.manualfetch.yml run --rm ingestion` | ✅ Required |
| Database migrations | `docker compose run --rm ingestion migrate up` | ✅ Required |
| Backtest | `run.bat backtest` or `docker compose run --rm ml_service python main.py backtest` | ✅ Required |

---

## Deprecated Commands

The following local execution commands are **DEPRECATED** and will error:

```bash
# ❌ DEPRECATED - DO NOT USE
cd ingestion && make run              # Use: make docker-worker
cd ingestion && make manualfetch      # Use: make docker-manualfetch  
cd ingestion && make migrate-up       # Use: make docker-migrate-up
cd ingestion && go run ./cmd/worker   # Use: docker compose up -d ingestion
python main.py predict                # Use: docker compose run --rm ml_service python main.py predict
```

---

## Entry Points

### Primary Entry Point: `run.bat` / `run.sh`

All user-facing commands go through the unified entry point:

```batch
# Windows
run.bat train           # Train models
run.bat predict --week 15  # Get predictions
run.bat backtest        # Run backtest
run.bat status          # Check system status

# Linux/Mac
./run.sh train
./run.sh predict --week 15
```

These scripts internally use `docker compose run --rm ml_service ...` ensuring Docker execution.

### ML Service Entry Point: `main.py`

The single Python entry point inside Docker:

```python
# This runs INSIDE the Docker container
python main.py [command]

# Commands:
# - pipeline    : Full training pipeline
# - train       : Train enhanced models
# - predict     : Generate predictions
# - backtest    : Run backtests
# - compare     : Compare model performance
```

---

## GitHub Actions Workflows

All GitHub Actions workflows run Python/Go operations inside Docker:

### CI/CD (`ci.yml`)
- Unit tests run on runner (acceptable for speed)
- Integration tests run via Docker containers
- Docker images are built and tested

### Model Monitor (`model_monitor.yml`)
- Starts services via `docker compose up -d`
- Runs analysis via `docker compose run --rm ml_service python ...`
- All database operations through Docker

### Model Retrain (`model_retrain.yml`)
- Training runs via `docker compose run --rm ml_service python scripts/...`
- Model validation inside Docker
- Deployment updates Docker images

---

## Docker Compose Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Development/default configuration |
| `docker-compose.prod.yml` | Production with resource limits |
| `docker-compose.manualfetch.yml` | Override for manual fetch operations |
| `monitoring/docker-compose.monitoring.yml` | Prometheus/Grafana monitoring |

---

## Enforcement

### Makefile Guards

The `ingestion/Makefile` has guards that prevent local execution:

```makefile
run: ## DEPRECATED: Use 'make docker-worker' instead
    @echo "⚠️  DEPRECATED: Local execution is not supported."
    @echo "Use: make docker-worker"
    @exit 1
```

### Path Assumptions

The `main.py` entry point assumes Docker paths:
- `MODEL_PATH=/app/models`
- Database host: `postgres` (Docker network)
- Redis host: `redis` (Docker network)

Running outside Docker will fail due to missing paths/services.

---

## Troubleshooting

### "Connection refused" errors
- **Cause**: Trying to run locally instead of Docker
- **Fix**: Use `docker compose run --rm ml_service ...`

### "Models not found" errors
- **Cause**: Wrong model path (not `/app/models`)
- **Fix**: Ensure running inside Docker container

### "Database connection failed"
- **Cause**: Database host is `postgres` (Docker network name)
- **Fix**: Use Docker compose which sets up the network

---

## Summary

| ✅ Do | ❌ Don't |
|-------|----------|
| `docker compose up -d` | `go run ./cmd/worker` |
| `run.bat predict` | `python main.py predict` (outside Docker) |
| `make docker-worker` | `make run` |
| `docker compose run --rm ml_service ...` | Direct Python execution |
