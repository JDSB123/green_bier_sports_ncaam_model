# Docker-Only Execution Policy

## Overview

**ALL operations MUST run through Docker containers.** No direct script execution outside Docker is supported or allowed.

## Why Docker-Only?

1. **Consistency**: Same environment for development, testing, and production
2. **Isolation**: No conflicts with local Python/Go versions
3. **Reproducibility**: Guaranteed dependencies and versions
4. **Security**: Contained execution with proper permissions
5. **Hardening**: All operations go through validated entry points

## Entry Points

### Primary Entry Point: `run.bat` (Windows) / `run.sh` (Linux/Mac)

```bash
# All commands go through this wrapper
run.bat predict --week 15 --season 2024
run.bat train
run.bat status
```

### Inside Docker: `main.py`

```bash
# This runs INSIDE the container
docker compose run --rm ml_service python main.py predict --week 15
```

## Forbidden Patterns

❌ **DO NOT** run scripts directly:
```bash
# WRONG - Don't do this
python ml_service/main.py predict
python ml_service/scripts/train_xgboost.py
go run ingestion/cmd/worker/main.go
```

✅ **DO** use Docker:
```bash
# CORRECT - Always use Docker
docker compose run --rm ml_service python main.py predict
docker compose run --rm ml_service python main.py train
docker compose up -d ingestion
```

## Single Source of Truth

All prediction logic goes through:
- **Service**: `src/services/prediction_service.py`
- **CLI**: `main.py` (uses PredictionService)
- **API**: `src/api/main.py` (uses PredictionService)

Both CLI and API use the same `PredictionService` - no duplication.

## Validation

The system enforces Docker-only execution by:
1. All scripts assume `/app` working directory (Docker path)
2. Database connections use Docker service names (`postgres`, `redis`)
3. Model paths assume Docker volume mounts (`/app/models`)
4. No local file system dependencies

## Troubleshooting

### "Module not found" errors
- **Cause**: Running outside Docker
- **Fix**: Use `docker compose run --rm ml_service python main.py [command]`

### "Database connection failed"
- **Cause**: Not using Docker service names
- **Fix**: Ensure using `docker compose` which sets up service networking

### "Models not found"
- **Cause**: Models not in Docker volume
- **Fix**: Models should be in `ml_service/models/` (mounted as `/app/models`)

## Migration Guide

If you have scripts that run directly:

**Before:**
```bash
cd ml_service
python main.py predict
```

**After:**
```bash
docker compose run --rm ml_service python main.py predict
```

Or use the wrapper:
```bash
run.bat predict
```

## CI/CD

All GitHub Actions workflows use Docker:
- Tests run in containers
- Training runs in containers
- Deployment uses container images

See `.github/workflows/` for examples.
