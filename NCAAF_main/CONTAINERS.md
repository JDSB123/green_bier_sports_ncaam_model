# NCAAF v5.0 Container Guide

This project provides two self-contained container options:

## 1. Backtest Container (Development/Testing)

**Purpose:** Self-contained environment for running backtests and model validation.

**Files:**
- `Dockerfile.backtest` - Backtest container image
- `docker-compose.backtest.yml` - Backtest compose configuration

**Usage:**

```bash
# Start backtest container
docker-compose -f docker-compose.backtest.yml up -d

# Run backtest
docker-compose -f docker-compose.backtest.yml exec backtest python3 main.py backtest --start-date 2024-09-01 --end-date 2024-12-17

# Or run interactively
docker-compose -f docker-compose.backtest.yml run --rm backtest python3 main.py backtest --start-date 2024-09-01 --end-date 2024-12-17

# View logs
docker-compose -f docker-compose.backtest.yml logs -f

# Stop container
docker-compose -f docker-compose.backtest.yml down
```

**Features:**
- ✅ PostgreSQL database (internal)
- ✅ Redis cache (internal)
- ✅ Python ML service with backtest scripts
- ✅ All credentials/config included
- ✅ No external dependencies required

**Environment Variables:**
- `DATABASE_PASSWORD` - Database password (required)
- `BACKTEST_START_DATE` - Start date for backtest (default: 2024-09-01)
- `BACKTEST_END_DATE` - End date for backtest (default: 2024-12-17)
- `DATABASE_NAME` - Database name (default: ncaaf_v5)
- `DATABASE_USER` - Database user (default: ncaaf_user)

---

## 2. Production Live Container (Ready to Roll)

**Purpose:** Self-contained production environment with all services, API, and proven model.

**Files:**
- `Dockerfile.prod` - Production container image
- `docker-compose.prod-live.yml` - Production compose configuration

**Prerequisites:**
1. ✅ Proven model trained and placed in `ml_service/models/`
2. ✅ All environment variables set in `.env` file
3. ✅ Model validated through backtesting

**Usage:**

```bash
# Start production container
docker-compose -f docker-compose.prod-live.yml up -d

# Check health
curl http://localhost:8001/health

# Get predictions
curl http://localhost:8001/api/v1/predictions/week/2024/15

# View logs
docker-compose -f docker-compose.prod-live.yml logs -f

# Stop container
docker-compose -f docker-compose.prod-live.yml down
```

**Features:**
- ✅ PostgreSQL database (internal)
- ✅ Redis cache (internal)
- ✅ Go ingestion service (worker)
- ✅ Python ML service with FastAPI
- ✅ All credentials/config included
- ✅ Production-ready with resource limits
- ✅ Health checks and monitoring
- ✅ Automatic restarts

**Environment Variables (Required):**
- `SPORTSDATA_API_KEY` - SportsDataIO API key
- `DATABASE_PASSWORD` - Database password
- `REDIS_PASSWORD` - Redis password (optional but recommended)
- `WEBHOOK_SECRET` - Webhook secret (if using webhooks)

**Ports:**
- `8001` - ML Service API (mapped from container port 8000)
- `8083` - Ingestion API (mapped from container port 8080)

---

## Other Container Options

### Development Container
- **File:** `docker-compose.yml`
- **Purpose:** Development environment with unified container
- **Usage:** `docker-compose up -d`

### Production (Separate Containers)
- **File:** `docker-compose.prod.yml`
- **Purpose:** Production with separate containers (better for scaling)
- **Usage:** `docker-compose -f docker-compose.prod.yml up -d`

### Manual Fetch
- **File:** `docker-compose.manualfetch.yml`
- **Purpose:** Override for manual data fetching
- **Usage:** `docker-compose -f docker-compose.yml -f docker-compose.manualfetch.yml run --rm ingestion manualfetch`

---

## Container Comparison

| Feature | Backtest | Production Live | Development |
|---------|----------|-----------------|-------------|
| PostgreSQL | ✅ Internal | ✅ Internal | ✅ Internal |
| Redis | ✅ Internal | ✅ Internal | ✅ Internal |
| ML Service | ✅ Python | ✅ Python + API | ✅ Python + API |
| Ingestion | ❌ | ✅ Go Worker | ✅ Go Worker |
| Backtest Scripts | ✅ | ❌ | ✅ |
| API Endpoints | ❌ | ✅ | ✅ |
| Resource Limits | ❌ | ✅ | ❌ |
| Health Checks | ✅ Basic | ✅ Full | ✅ Basic |

---

## Migration Path

1. **Development/Testing:** Use `docker-compose.backtest.yml` to validate models
2. **Model Validation:** Run backtests and ensure ROI/performance metrics are acceptable
3. **Production Deployment:** Once model is proven, use `docker-compose.prod-live.yml` to roll live

---

## Cleanup

To remove old/unused containers:

```bash
# List all containers
docker ps -a | grep ncaaf

# Stop and remove specific container
docker stop <container_name>
docker rm <container_name>

# Remove unused volumes
docker volume prune

# Remove unused images
docker image prune
```

---

## Troubleshooting

### Backtest Container

**Issue:** Database not ready
```bash
# Wait for database initialization
docker-compose -f docker-compose.backtest.yml logs backtest | grep "Database initialized"
```

**Issue:** Models not found
```bash
# Ensure models are in ml_service/models/
ls -la ml_service/models/enhanced/
```

### Production Container

**Issue:** API not responding
```bash
# Check health
curl http://localhost:8001/health

# Check logs
docker-compose -f docker-compose.prod-live.yml logs ml_service
```

**Issue:** Ingestion not working
```bash
# Check ingestion logs
docker-compose -f docker-compose.prod-live.yml logs ingestion

# Verify API key
docker-compose -f docker-compose.prod-live.yml exec ncaaf_prod_live env | grep SPORTSDATA_API_KEY
```
