# Manual-Only Mode - Zero Automation

**Date:** December 20, 2025
**Status:** ✅ ENFORCED

---

## Overview

This system keeps prediction runs **100% manual-only**—no polling, cron jobs, or scheduled tasks automatically trigger picks.
Deployments are also operator-initiated (see `azure/deploy.ps1`). Nothing auto-deploys or auto-runs predictions.

You control when data is synced and predictions are run.

---

## What's Disabled

### ❌ No Continuous Polling
- Rust odds-ingestion service: Removed continuous polling loop
- Default `RUN_ONCE=true` (cannot be disabled)
- Service runs once and exits immediately

### ❌ No Cron Schedulers
- Go ratings-sync service: Removed cron scheduler
- No daily 6 AM ET automatic sync
- Default `RUN_ONCE=true` (cannot be disabled)
- Service runs once and exits immediately

### ❌ No Background Daemons
- `start.sh` no longer starts ratings-sync or odds-ingestion as daemons
- Only starts the Python API server for manual predictions
- Binaries are called directly by `run_today.py` when you want fresh data

### ❌ Release Automation is Separate
- Deployments are run manually via `azure/deploy.ps1`
- Deploy **never** runs predictions, sync jobs, or backtests automatically
- Operators still choose when to execute `run_today.py` (inside the container) or backtesting scripts

### ❌ No Automated Backtesting
- No background backtesting tasks
- No scheduled backtest runs
- Backtesting is manual-only (see `MODEL_BACKTEST_AND_INDEPENDENCE_CONFIRMATION.md`)

---

## How It Works

### Manual Trigger: `run_today.py`

When you run `run_today.py` (inside the prediction-service container):

1. **Starts containers** (postgres, redis, prediction-service)
2. **Calls `run_today.py`** inside the container
3. **Syncs fresh data** (only when you run it):
   - Calls `/app/bin/ratings-sync` with `RUN_ONCE=true`
   - Calls `/app/bin/odds-ingestion` with `RUN_ONCE=true`
   - Both run once and exit immediately
4. **Runs predictions** on fresh data
5. **Outputs recommendations** to console
6. **Exits** - no background processes continue running

### What Runs Continuously

**Only the API server** (if you need it):
- Python FastAPI server on port 8092
- Only for manual HTTP requests
- No automated data syncing

**Database and Redis** (data storage):
- PostgreSQL/TimescaleDB
- Redis cache
- Just store data, don't trigger anything

---

## Code Changes Made

### Rust Service (`services/odds-ingestion-rust/src/main.rs`)

**Removed:**
- Continuous polling loop (`run()` method still exists but is unreachable)
- Default changed: `RUN_ONCE=true` (was `false`)
- Error if `RUN_ONCE=false` is set

**Result:** Service always runs once and exits

### Go Service (`services/ratings-sync-go/main.go`)

**Removed:**
- Cron scheduler (import removed)
- Daily 6 AM ET automatic sync
- Startup sync on container start
- Default changed: `RUN_ONCE=true` (was `false`)
- Error if `RUN_ONCE=false` is set

**Result:** Service always runs once and exits

### Start Script (`services/prediction-service-python/start.sh`)

**Removed:**
- Background daemon for ratings-sync
- Background daemon for odds-ingestion

**Result:** Only starts API server, no background sync processes

### Docker Compose (`docker-compose.yml`)

**Changed:**
- `RUN_ONCE: "${RATINGS_RUN_ONCE:-true}"` (default true)
- Removed `POLL_INTERVAL_SECONDS` usage note (not used)

---

## Usage

### Get Fresh Picks (Manual)

```bash
# Start dependencies + API container (if not already running)
docker compose up -d postgres redis prediction-service

# Run predictions with fresh data sync
docker compose exec prediction-service python /app/run_today.py

# Skip data sync (use cached data)
docker compose exec prediction-service python /app/run_today.py --no-sync

# Specific game
docker compose exec prediction-service python /app/run_today.py --game "Duke" "UNC"

# Specific date
docker compose exec prediction-service python /app/run_today.py --date 2025-12-20
```

### What Happens

1. Containers start (postgres, redis, prediction-service)
2. `run_today.py` executes inside container
3. **Manual sync triggers:**
   ```bash
   /app/bin/ratings-sync    # RUN_ONCE=true - syncs once and exits
   /app/bin/odds-ingestion  # RUN_ONCE=true - syncs once and exits
   ```
4. Predictions run on fresh data
5. Recommendations displayed
6. Script exits

**No background processes continue running.**

---

## Verification

### Check No Automation

```bash
# Verify no cron jobs
docker compose exec prediction-service crontab -l
# Should show: "no crontab for ncaam"

# Verify processes (should only see API server, not sync daemons)
docker compose exec prediction-service ps aux
# Should NOT see: ratings-sync or odds-ingestion running as daemons

# Check environment
docker compose exec prediction-service env | grep RUN_ONCE
# Should show: RUN_ONCE=true
```

---

## Summary

✅ **Manual-only** - You control when data syncs
✅ **No polling** - Services run once and exit
✅ **No cron** - No scheduled tasks
✅ **No daemons** - No background sync processes
✅ **Release automation only** - CI/CD builds/pushes containers but never runs predictions
✅ **No automated backtesting** - All backtesting is manual-only

**You run `run_today.py` when you want fresh picks. That's it.**

---

**Last Updated:** December 20, 2025
**Enforcement:** Compile-time and runtime checks prevent automation
