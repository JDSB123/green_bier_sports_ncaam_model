# Unified Container Architecture - NCAAF v5.0

## Overview

NCAAF v5.0 now runs in a **single unified container** containing all services:
- PostgreSQL (embedded, localhost only)
- Redis (embedded, localhost only)
- Ingestion Service (Go)
- ML Service (Python/FastAPI)

## Benefits

1. **Simplified Deployment** - One container to manage instead of four
2. **No Port Conflicts** - Database and Redis are internal only
3. **Easier Management** - Single container lifecycle
4. **Resource Efficient** - Shared resources, no network overhead between services

## Container Structure

```
ncaaf_v5 (single container)
├── PostgreSQL (localhost:5432) - Internal only
├── Redis (localhost:6379) - Internal only
├── Ingestion API (0.0.0.0:8080) → Host:8083
└── ML Service API (0.0.0.0:8000) → Host:8001
```

## Port Mappings

| Service | Internal | External | Purpose |
|---------|----------|----------|---------|
| ML Service | 8000 | **8001** | Predictions API |
| Ingestion | 8080 | **8083** | Data ingestion API |
| PostgreSQL | 5432 | None | Internal only |
| Redis | 6379 | None | Internal only |

## Usage

### Start Container
```bash
run.bat start
# or
docker compose up -d
```

### Stop Container
```bash
run.bat stop
# or
docker compose down
```

### View Logs
```bash
run.bat logs
# or
docker compose logs -f ncaaf_v5
```

### Run Commands
```bash
# Run backtest
run.bat backtest

# Make predictions
run.bat predict --week 15

# Train models
run.bat train
```

## Internal Services

All services communicate via `localhost`:
- ML Service → PostgreSQL: `localhost:5432`
- ML Service → Redis: `localhost:6379`
- Ingestion → PostgreSQL: `localhost:5432`
- Ingestion → Redis: `localhost:6379`

## Process Management

Supervisor manages all processes:
- `postgres` - Database server
- `redis` - Cache server
- `ml_service` - Python FastAPI service
- `ingestion` - Go worker service

## Data Persistence

Volumes are mounted for:
- `/var/lib/postgresql/16/main` - Database data
- `/app/models` - Trained ML models
- `/app/logs` - Service logs

## Health Checks

Container health is checked via ML Service endpoint:
- `http://localhost:8000/health`
- Checks every 30 seconds
- 60 second startup grace period

## Security

- All services run with `no-new-privileges:true`
- Database and Redis only accessible from localhost
- Non-root user for application code
- Read-only schema volume
