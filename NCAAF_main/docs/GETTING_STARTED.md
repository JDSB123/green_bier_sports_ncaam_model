# Getting Started with NCAAF v5.0 BETA

Complete guide to setting up and running the NCAAF v5.0 prediction system.

## Prerequisites

### Required Software

- **Docker Desktop** (Windows/Mac) or Docker Engine (Linux)
  - Download: https://www.docker.com/products/docker-desktop
  - Minimum: Docker 20.10+, Docker Compose 2.0+

- **SportsDataIO API Key**
  - Sign up: https://sportsdata.io/
  - Subscription: CFB (College Football) API access required
  - Free trial available for testing

### Optional (for local development)

- **Go 1.23+** - For developing the ingestion service
  - Download: https://go.dev/dl/

- **Python 3.12+** - For developing the ML service
  - Download: https://www.python.org/downloads/

- **PostgreSQL 16+** - For local database access
  - Download: https://www.postgresql.org/download/

## Quick Start (Docker)

### 1. Clone the Repository

```bash
cd C:\Users\JB\green-bier-ventures
cd ncaaf_v5.0_BETA
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env file and add your API key
# On Windows, use: notepad .env
# On Mac/Linux, use: nano .env or vim .env
```

**Required settings in .env:**

```env
# CRITICAL: Add your SportsDataIO API key
SPORTSDATA_API_KEY=your_actual_api_key_here

# Database password (change in production!)
DATABASE_PASSWORD=secure_password_here

# Webhook secret (change in production!)
WEBHOOK_SECRET=random_secret_key_here
```

### 3. Start All Services

```bash
# Start PostgreSQL, Redis, ingestion service, and ML service
docker-compose up -d

# View logs
docker-compose logs -f
```

**Expected output:**

```
ncaaf_v5_postgres    | database system is ready to accept connections
ncaaf_v5_redis       | Ready to accept connections
ncaaf_v5_ingestion   | Starting NCAAF v5.0 Data Ingestion Worker
ncaaf_v5_ingestion   | Configuration loaded
ncaaf_v5_ingestion   | SportsDataIO client initialized
ncaaf_v5_ingestion   | Running initial data sync...
ncaaf_v5_ingestion   | Teams fetched: 133
ncaaf_v5_ingestion   | Stadiums fetched: 95
ncaaf_v5_ingestion   | Scheduler starting...
ncaaf_v5_ml_service  | INFO:     Started server process
ncaaf_v5_ml_service  | INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 4. Verify Services

**Check ingestion service health:**

```bash
curl http://localhost:8080/health
```

**Expected response:**

```json
{
  "status": "healthy",
  "environment": "development"
}
```

**Check ML service health:**

```bash
curl http://localhost:8000/health
```

**Expected response:**

```json
{
  "status": "healthy",
  "environment": "development"
}
```

### 5. Verify Data Ingestion

**Check teams loaded:**

```bash
curl http://localhost:8000/api/v1/teams
```

**Expected response:**

```json
{
  "count": 133,
  "teams": [
    {
      "team_id": 1,
      "team_code": "ALA",
      "school_name": "Alabama",
      "mascot": "Crimson Tide",
      "conference": "SEC"
    },
    ...
  ]
}
```

**Check games for current week:**

```bash
# Replace 2025 and 15 with current season and week
curl http://localhost:8000/api/v1/games/week/2025/15
```

### 6. Monitor Logs

```bash
# Follow all logs
docker-compose logs -f

# Follow specific service
docker-compose logs -f ingestion
docker-compose logs -f ml_service

# View recent logs
docker-compose logs --tail=100 ingestion
```

## Next Steps

### Generate Predictions

Once games are loaded, generate predictions:

```bash
# Get predictions for week 15 of 2025 season
curl http://localhost:8000/api/v1/predictions/week/2025/15
```

**Note**: The prediction pipeline is still in development. For now, you'll see:

```json
{
  "season": 2025,
  "week": 15,
  "count": 10,
  "predictions": [],
  "message": "Prediction pipeline not yet implemented - coming soon!"
}
```

### Access Database

Connect to PostgreSQL to explore data:

```bash
# Connection details
Host: localhost
Port: 5432
Database: ncaaf_v5
User: ncaaf_user
Password: <from your .env file>
```

**Using psql:**

```bash
docker-compose exec postgres psql -U ncaaf_user -d ncaaf_v5
```

**Useful queries:**

```sql
-- Count teams
SELECT COUNT(*) FROM teams;

-- View recent games
SELECT * FROM games
ORDER BY game_date DESC
LIMIT 10;

-- View active games
SELECT * FROM active_games;

-- View latest odds
SELECT * FROM latest_odds
LIMIT 10;
```

### Access Redis Cache

```bash
# Connect to Redis CLI
docker-compose exec redis redis-cli

# View cached keys
KEYS *

# View team cache
GET team:1
```

## Local Development

### Go Ingestion Service

```bash
cd ingestion

# Install dependencies
go mod download

# Run tests
go test ./...

# Build binary
make build

# Run locally (requires PostgreSQL and Redis running)
make run
```

### Python ML Service

```bash
cd ml_service

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest

# Run API server locally
uvicorn src.api.main:app --reload --port 8000
```

## Common Tasks

### Stop Services

```bash
docker-compose down
```

### Stop and Remove Data

```bash
# WARNING: This deletes all data!
docker-compose down -v
```

### Restart Single Service

```bash
# Restart ingestion service
docker-compose restart ingestion

# Restart ML service
docker-compose restart ml_service
```

### View Database Logs

```bash
docker-compose logs postgres
```

### Rebuild After Code Changes

```bash
# Rebuild ingestion service
docker-compose build ingestion

# Rebuild ML service
docker-compose build ml_service

# Rebuild and restart
docker-compose up -d --build
```

## Troubleshooting

### Problem: API Key Error

```
ERROR: SPORTSDATA_API_KEY is required
```

**Solution**: Add your API key to `.env` file:

```env
SPORTSDATA_API_KEY=your_actual_key_here
```

### Problem: Database Connection Failed

```
ERROR: failed to connect to database
```

**Solution**: Ensure PostgreSQL is running:

```bash
docker-compose ps postgres
docker-compose logs postgres
```

### Problem: Port Already in Use

```
ERROR: port is already allocated
```

**Solution**: Stop conflicting services or change port in `.env`:

```env
INGESTION_PORT=8081  # instead of 8080
ML_SERVICE_PORT=8001  # instead of 8000
```

### Problem: No Teams Loaded

```
{"count": 0, "teams": []}
```

**Solution**: Check ingestion service logs:

```bash
docker-compose logs ingestion

# Verify API key is correct
# Verify initial sync completed successfully
```

### Problem: Slow Performance

```bash
# Check container resource usage
docker stats

# Increase Docker Desktop resources:
# Settings → Resources → Advanced
# - CPUs: 4+
# - Memory: 8GB+
```

## Configuration

### Key Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SPORTSDATA_API_KEY` | SportsDataIO API key (required) | - |
| `DATABASE_PASSWORD` | PostgreSQL password | ncaaf_password |
| `WORKER_INTERVAL` | Polling interval (seconds) | 60 |
| `ENABLE_SCHEDULER` | Enable background scheduler | true |
| `ENABLE_WEBHOOKS` | Enable webhook server | true |
| `LOG_LEVEL` | Logging level | info |
| `APP_ENV` | Environment (development/production) | development |

See `.env.example` for full list of configuration options.

## Data Flow Overview

```
1. Initial Sync (on startup)
   ↓
   Fetch teams, stadiums, schedule from SportsDataIO
   ↓
   Store in PostgreSQL

2. Background Worker (every 60s)
   ↓
   Query PostgreSQL for active games
   ↓
   Fetch odds for active games only
   ↓
   Update PostgreSQL and Redis cache

3. Nightly Refresh (2 AM)
   ↓
   Refresh teams, stadiums, schedules
   ↓
   Update PostgreSQL

4. Prediction Request
   ↓
   Load game data from PostgreSQL
   ↓
   Extract features
   ↓
   Run ML models
   ↓
   Generate predictions
   ↓
   Return to client
```

## What's Next?

### Immediate Next Steps

1. **Complete Prediction Pipeline**
   - Implement feature engineering
   - Load and run XGBoost models
   - Generate betting recommendations

2. **Model Training**
   - Create training scripts
   - Train on historical data
   - Validate model performance

3. **Backtesting**
   - Implement backtesting framework
   - Validate against 2023-2025 data
   - Calculate ROI and accuracy

### Future Enhancements

- Real-time dashboard (web UI)
- Automated bet tracking
- CLV (Closing Line Value) analysis
- Slack/Discord notifications for picks
- Kubernetes deployment
- ML model versioning
- A/B testing framework

## Support

### Logs Location

```bash
# Docker container logs
docker-compose logs [service_name]

# Persistent logs (if configured)
./ingestion/logs/
./ml_service/logs/
```

### Database Backups

```bash
# Backup database
docker-compose exec postgres pg_dump -U ncaaf_user ncaaf_v5 > backup.sql

# Restore database
docker-compose exec -T postgres psql -U ncaaf_user -d ncaaf_v5 < backup.sql
```

### Health Checks

All services expose `/health` endpoints for monitoring:

- Ingestion Service: `http://localhost:8080/health`
- ML Service: `http://localhost:8000/health`

### Documentation

- [Architecture](./ARCHITECTURE.md)
- [SportsDataIO Workflow](./SPORTSDATAIO_WORKFLOW.md)
- [Main README](../README.md)

## Resources

- SportsDataIO API Docs: https://sportsdata.io/developers
- Docker Documentation: https://docs.docker.com/
- PostgreSQL Documentation: https://www.postgresql.org/docs/
- FastAPI Documentation: https://fastapi.tiangolo.com/
- Go Documentation: https://go.dev/doc/
