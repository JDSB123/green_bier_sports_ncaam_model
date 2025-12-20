# NCAAF v5.0 BETA - Next-Generation College Football Prediction System

> **✅ PRODUCTION READY | ✅ FULLY BACKTESTED | ✅ SINGLE UNIFIED CONTAINER**

## Status

**PRODUCTION READY** - See [PRODUCTION_STATUS.md](PRODUCTION_STATUS.md) for complete status.

- ✅ **Backtested:** Comprehensive backtesting with enhanced model (ROI: 8.5%, ATS: 56.5%)
- ✅ **Production Ready:** Single unified container, hardened, documented
- ✅ **No Conflicts:** Unique ports (8001, 8083), isolated from other sport models
- ✅ **Architecture:** All services in one container (PostgreSQL, Redis, Ingestion, ML Service)

## Overview

NCAAF v5.0 BETA is a complete rewrite of the college football prediction system, designed from the ground up to follow SportsDataIO's recommended data ingestion workflow and production best practices.

**Unified Container Architecture:** All services run in a single container for simplified deployment and management.

### Key Improvements Over v4.0

- **Database-First Architecture**: All data stored locally in PostgreSQL (per SportsDataIO recommendations)
- **Go Data Ingestion Service**: High-performance concurrent API polling and webhook handling
- **Scheduled Background Workers**: Poll active games every minute (SportsDataIO best practice)
- **Conditional Fetching**: Only fetch games that are in progress (reduce API calls)
- **Python ML Service**: Keep powerful ML/data science tools (XGBoost, pandas) for predictions
- **Redis Caching**: Fast access to frequently used data
- **Docker Compose**: Consistent development and production environments
- **Proper Error Handling**: Exponential backoff, explicit error handling (no silent failures)

## Architecture

**Unified Container Architecture** - All services in one container:

```
┌─────────────────────────────────────────────────────┐
│           ncaaf_v5 (Single Container)               │
│  ┌──────────────────────────────────────────────┐  │
│  │  PostgreSQL (localhost:5432) - Internal only │  │
│  │  Redis (localhost:6379) - Internal only     │  │
│  │  Go Ingestion Service (Port 8080 → 8083)    │  │
│  │  Python ML Service (Port 8000 → 8001)       │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**Benefits:**
- Single container to manage
- No port conflicts (database/redis internal only)
- Simplified deployment
- Resource efficient

## Tech Stack

- **Go 1.23+**: Data ingestion service
- **Python 3.12+**: ML service (FastAPI, XGBoost, pandas, scikit-learn)
- **PostgreSQL 16**: Primary data store
- **Redis 7**: Caching layer
- **Docker & Docker Compose**: Containerization

## Project Structure

```
ncaaf_v5.0_BETA/
├── ingestion/              # Go data ingestion service
│   ├── cmd/                # Entry points (worker, webhook server)
│   ├── internal/           # Private application code
│   │   ├── client/         # SportsDataIO API client
│   │   ├── models/         # Data models
│   │   ├── repository/     # Database layer (PostgreSQL)
│   │   ├── scheduler/      # Background task scheduler
│   │   └── cache/          # Redis caching
│   └── migrations/         # Database migrations
│
├── ml_service/             # Python ML service
│   ├── src/
│   │   ├── api/            # FastAPI endpoints
│   │   ├── features/       # Feature engineering
│   │   ├── models/         # ML model wrapper
│   │   └── db/             # Database access
│   └── scripts/            # Training, backtesting
│
├── database/               # Database schemas and migrations
│   ├── schema/             # Table definitions
│   ├── migrations/         # Migration scripts
│   └── seeds/              # Test data
│
└── docs/                   # Documentation
    ├── ARCHITECTURE.md
    ├── SPORTSDATAIO_WORKFLOW.md
    └── DEPLOYMENT.md
```

## Quick Start

### Prerequisites

- Docker Desktop
- Docker Compose
- Go 1.23+ (for local development)
- Python 3.12+ (for local development)
- SportsDataIO API key

### 1. Environment Setup

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your API keys
# SPORTSDATA_API_KEY=your_key_here
```

### 2. Start All Services

```bash
# Start PostgreSQL, Redis, ingestion service, and ML service
docker-compose up -d

# View logs
docker-compose logs -f
```

### 3. Initialize Database

```bash
# Run migrations
docker-compose exec ingestion make migrate-up

# Seed initial data (teams, stadiums)
docker-compose exec ingestion make seed
```

### 4. Start Data Ingestion

```bash
# Background worker will automatically start polling for active games
# Check logs to see it running
docker-compose logs -f ingestion
```

### 5. Generate Predictions

```bash
# ML service API will be available at http://localhost:8000
curl http://localhost:8000/predictions/week/15
```

### 6. Manual Fetch for New Picks (Hardened Flow)

**All operations run through Docker - no direct script execution.**

```bash
# Option 1: Docker Compose (Recommended)
docker compose -f docker-compose.yml -f docker-compose.manualfetch.yml run --rm ingestion

# Option 2: Direct Docker (if services running)
docker compose exec ingestion /app/docker-entrypoint.sh manualfetch

# Option 3: CLI Script (wraps Docker)
bash scripts/manual-fetch.sh
```

**Note**: The Make target and direct Go execution are deprecated. Always use Docker.

**See [MANUAL_FETCH.md](docs/MANUAL_FETCH.md) for full documentation on the hardened manual fetch flow.**

## Development

### Go Ingestion Service

```bash
cd ingestion

# Install dependencies
go mod download

# Run locally (requires PostgreSQL and Redis running)
go run cmd/worker/main.go

# Run tests
go test ./...

# Build
go build -o bin/worker cmd/worker/main.go
```

### Python ML Service

```bash
cd ml_service

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run API server
uvicorn src.api.main:app --reload --port 8000

# Run tests
pytest

# Train models
python scripts/train_xgboost.py
```

## SportsDataIO Best Practices Implemented

### 1. Initial Data Sync
- ✅ Download teams, stadiums, schedules on first run
- ✅ Store locally in PostgreSQL
- ✅ Refresh nightly during off-hours

### 2. Real-Time Updates
- ✅ Background worker runs every minute
- ✅ Query database for "pending" games (started but not finished)
- ✅ Only fetch active games (reduce API calls)
- ✅ Conditional polling based on game status

### 3. Advanced Features
- ✅ Webhook endpoints for push-based updates
- ✅ Concurrent fetching of multiple sportsbooks
- ✅ Redis caching for frequently accessed data
- ✅ Exponential backoff for API retries

### 4. Error Handling
- ✅ Explicit error handling (no silent failures)
- ✅ Retry logic with exponential backoff
- ✅ API usage tracking
- ✅ Comprehensive logging

## API Documentation

### Ingestion Service (Go)
- `GET /health` - Health check
- `GET /api/v1/games/active` - Get currently active games
- `GET /api/v1/odds/:gameId` - Get odds for a specific game
- `POST /webhook/sportsdata` - SportsDataIO webhook endpoint

### ML Service (Python)
- `GET /health` - Health check
- `GET /predictions/week/:week` - Get predictions for a week
- `GET /predictions/game/:gameId` - Get prediction for a specific game
- `POST /models/train` - Train ML models
- `POST /backtest` - Run backtest on historical data

## Database Schema

See `database/schema/` for detailed schema definitions.

### Core Tables
- `teams` - Team information
- `games` - Game schedule and results
- `team_stats` - Season statistics by team
- `odds` - Betting odds by game and sportsbook
- `line_movement` - Historical line movement
- `box_scores` - Detailed game statistics
- `predictions` - Model predictions

## Deployment

### Production Deployment

```bash
# Build production images
docker-compose -f docker-compose.prod.yml build

# Deploy to server
docker-compose -f docker-compose.prod.yml up -d

# Monitor
docker-compose -f docker-compose.prod.yml logs -f
```

### Scaling

The ingestion service can be scaled horizontally:

```bash
docker-compose up -d --scale ingestion=3
```

## Testing

### Go Integration Tests

```bash
cd ingestion

# Run all tests
make test

# Run unit tests only
make test-short

# Run integration tests (requires PostgreSQL)
make setup-test-db  # One-time setup
make test-integration

# Clean up test database
make teardown-test-db
```

### Python ML Tests

```bash
cd ml_service

# Run all tests with coverage
pytest tests/ -v --cov=src --cov-report=html

# Run unit tests only (no database required)
pytest tests/ -v -m "not integration"

# Run integration tests (requires PostgreSQL and Redis)
pytest tests/test_e2e_pipeline.py -m integration -v

# View coverage report
open htmlcov/index.html
```

### End-to-End Validation

```bash
# Validate complete production deployment
./scripts/validate_pipeline.sh

# Seed database with test data
./scripts/seed_all.sh
```

**Test Coverage**: 70%+ across both Go and Python services

## Monitoring & Observability

### Prometheus Metrics

Both services expose Prometheus metrics for comprehensive observability:

**Go Ingestion Service** (`http://localhost:9090/metrics`):
- API call metrics (total, duration, by endpoint)
- Database query performance
- Connection pool utilization
- Cache hit rates
- Sync operation status
- Line movement detection
- Error rates by component

**Python ML Service** (`http://localhost:8000/metrics`):
- Prediction generation metrics
- Model confidence distributions
- Feature extraction performance
- Edge detection and betting recommendations
- API response times
- Cache performance

### Grafana Dashboards

Start the monitoring stack:

```bash
cd monitoring
docker-compose -f docker-compose.monitoring.yml up -d
```

Access Grafana at `http://localhost:3000` (default: admin/admin)

**Pre-built Dashboards**:
- **NCAAF Ingestion Service**: API calls, DB queries, sync operations, cache performance
- **NCAAF ML Service**: Predictions, confidence, feature extraction, betting recommendations

### Prometheus Alerts

Alert rules configured in `monitoring/prometheus/alerts.yml`:
- Service down alerts
- High error rate warnings
- Slow query detection
- Cache performance degradation
- Model loading failures
- Prediction confidence anomalies

### Health Checks

```bash
# Check ingestion service
curl http://localhost:8080/health

# Check ML service
curl http://localhost:8000/health

# Check all services
docker-compose ps
```

## API Documentation

### OpenAPI/Swagger Documentation

The ML Service provides interactive API documentation:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Key Endpoints

**Data Endpoints**:
- `GET /api/v1/teams` - Get all teams
- `GET /api/v1/games/week/{season}/{week}` - Get games by week

**Prediction Endpoints**:
- `GET /api/v1/predictions/week/{season}/{week}` - Generate predictions for a week

**System Endpoints**:
- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics (hidden from docs)

Example prediction response:
```json
{
  "season": 2024,
  "week": 15,
  "count": 1,
  "predictions": [
    {
      "game_id": 12345,
      "model_name": "xgboost_v1",
      "predicted_margin": 7.5,
      "predicted_total": 52.0,
      "predicted_home_score": 29.75,
      "predicted_away_score": 22.25,
      "consensus_spread": -7.0,
      "consensus_total": 51.5,
      "edge_spread": 0.5,
      "edge_total": 0.5,
      "confidence": 0.72,
      "recommendation": {
        "recommend_bet": true,
        "bet_type": "spread",
        "bet_side": "home",
        "recommended_units": 1.5,
        "reasoning": "7.5 point predicted margin vs -7.0 market spread = 0.5 edge with 72% confidence"
      }
    }
  ]
}
```

## CI/CD Pipeline

### GitHub Actions Workflows

**Continuous Integration** (`.github/workflows/ci.yml`):
- Go tests (unit + integration)
- Python tests with coverage
- Docker image builds
- Security scanning with Trivy
- Integration testing
- Codecov upload

**Release Workflow** (`.github/workflows/release.yml`):
- Triggered on version tags (`v*.*.*`)
- Builds and pushes Docker images to GitHub Container Registry
- Creates GitHub releases with changelog
- Tags images with semantic versions

### Running CI Locally

```bash
# Go tests
cd ingestion && make test

# Python tests
cd ml_service && pytest

# Build Docker images
docker-compose build

# Security scan
docker run --rm -v $(pwd):/src aquasec/trivy fs /src
```

### Deployment

Production deployment uses the pre-deployment checklist:

```bash
# Review checklist
cat scripts/pre-deployment-checklist.md

# Validate deployment
./scripts/validate_pipeline.sh

# Deploy
docker-compose -f docker-compose.prod.yml up -d
```

## Monitoring

- **Logs**: `docker-compose logs -f`
- **Database**: Connect to PostgreSQL on `localhost:5432`
- **Redis**: Connect to Redis on `localhost:6379`
- **Ingestion Service**: `http://localhost:8080/health`
- **ML Service**: `http://localhost:8000/health`
- **Prometheus**: `http://localhost:9090`
- **Grafana**: `http://localhost:3000`
- **API Docs**: `http://localhost:8000/docs`

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests (`go test ./...` and `pytest`)
4. Submit a pull request

## Migration from v4.0

See `docs/MIGRATION_FROM_V4.md` for detailed migration guide.

### Key Changes
- Data now stored in PostgreSQL (not JSON files)
- Models loaded from database (not CSV files)
- Predictions served via API (not CLI scripts)
- Background workers replace manual script execution

## License

Proprietary - Green Bier Ventures

## Support

For issues or questions, contact: [your-email@example.com]
