# System Architecture - NCAAM Sports Model

## Overview

This document describes how the system is organized and how different components work together.

---

## 🏗️ High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      CLIENT LAYER                               │
│  (Web Browser, Mobile App, Betting Platform Integration)        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API LAYER                                   │
│  FastAPI (Python)                                               │
│  └─ /predict          - Get predictions for upcoming games      │
│  └─ /picks            - Get today's recommended picks           │
│  └─ /history          - Get prediction history                  │
│  └─ /health           - System health check                     │
└────────────────────────┬────────────────────────────────────────┘
                         │
                ┌────────┴──────────┐
                ▼                   ▼
    ┌──────────────────────┐  ┌──────────────────────┐
    │  BUSINESS LOGIC      │  │  DATA INGESTION      │
    │  (ML Prediction)     │  │  (Ratings Sync)      │
    │                      │  │                      │
    │  Python Services:    │  │  Go Service:         │
    │  ├─ Load models      │  │  ├─ Fetch Barttorvik │
    │  ├─ Make predictions │  │  │   ratings         │
    │  ├─ Combine markets  │  │  ├─ Normalize teams  │
    │  └─ Cache results    │  │  └─ Store in DB      │
    │                      │  │                      │
    │  Models:             │  │  Schedule: Manual    │
    │  ├─ XGBoost Spread   │  │  (user triggered)    │
    │  ├─ XGBoost Total    │  │                      │
    │  └─ Ensemble         │  │                      │
    └──────────┬───────────┘  └──────────┬───────────┘
               │                         │
               └────────────┬────────────┘
                            ▼
            ┌───────────────────────────────────┐
            │      DATA LAYER                   │
            │                                   │
            │  PostgreSQL 15 (localhost:5432)   │
            │  ├─ teams                         │
            │  ├─ games                         │
            │  ├─ team_ratings                  │
            │  ├─ odds_snapshots                │
            │  ├─ predictions                   │
            │  └─ games_results                 │
            │                                   │
            │  Redis (localhost:6379)           │
            │  ├─ Prediction cache (TTL 4h)     │
            │  ├─ Odds snapshot cache (TTL 1h)  │
            │  └─ Session data                  │
            └───────────────────────────────────┘
```

---

## 📁 Directory Structure

```
green_bier_sports_ncaam_model/
│
├── services/                      # Microservices (Python + Go)
│   │
│   ├── prediction-service-python/ # Main API service (Python/FastAPI)
│   │   ├── main.py               # Entry point, FastAPI app
│   │   ├── models/               # ML model loading
│   │   ├── routes/               # API endpoints
│   │   ├── database/             # PostgreSQL connection
│   │   ├── cache/                # Redis operations
│   │   ├── requirements.txt       # Dependencies
│   │   └── tests/                # Unit tests
│   │
│   └── ratings-sync-go/          # Data ingestion service (Go)
│       ├── main.go               # Entry point
│       ├── barttorvik/           # API client for ratings
│       ├── database/             # PostgreSQL connection
│       ├── models/               # Data models
│       ├── go.mod                # Go module definition
│       ├── go.sum                # Go dependency checksums
│       └── tests/                # Unit tests
│
├── database/                      # Database schema & migrations
│   ├── migrations/               # SQL migration files
│   │   ├── 001_initial_schema.sql
│   │   ├── 002_add_predictions.sql
│   │   └── ...
│   ├── seeds/                    # Sample data
│   └── schema.sql                # Current schema
│
├── models/                        # ML model files (binary)
│   ├── xgboost_spread.pkl        # Spread prediction model
│   ├── xgboost_total.pkl         # Total prediction model
│   └── scaler.pkl                # Feature scaling
│
├── .devcontainer/                # Codespaces configuration
│   ├── devcontainer.json         # Environment setup
│   └── post-create.sh            # Auto-run after Codespaces boots
│
├── scripts/                       # Utility scripts
│   ├── setup-local-complete.ps1  # ONE master setup (Windows)
│   ├── verify-all.ps1            # System verification
│   ├── check-r-setup.ps1         # R installation check
│   └── ...
│
├── docs/                          # Documentation
│   ├── SETUP.md                  # Setup guide (READ FIRST!)
│   ├── QUICK_START.md            # TL;DR
│   ├── ARCHITECTURE.md           # This file
│   ├── API.md                    # API documentation
│   └── ...
│
├── tests/                         # Integration tests
│   ├── test_api.py
│   ├── test_predictions.py
│   └── test_database.py
│
├── .env.local                     # Local config (DO NOT COMMIT)
├── .gitignore                     # Git ignore rules
├── docker-compose.yml             # Container orchestration
├── pyproject.toml                 # Python project config
├── requirements-dev.txt           # Dev dependencies
├── README.md                      # Project overview
└── VERSION                        # Version number
```

---

## 🔄 Data Flow

### Prediction Request Flow

```
User Query (web/API)
  │
  ▼
FastAPI Endpoint (/predict)
  │
  ├─ Check Redis cache
  │  └─ If found: Return cached result (fast path, <1ms)
  │
  └─ If not cached:
      │
      ├─ Query PostgreSQL
      │  ├─ Get teams
      │  ├─ Get team ratings
      │  └─ Get recent odds
      │
      ├─ Load ML models
      │
      ├─ Prepare features
      │  ├─ Team rating offsets
      │  ├─ Home/away effects
      │  ├─ Historical data
      │  └─ Tempo adjustments
      │
      ├─ Run predictions
      │  ├─ XGBoost spread prediction
      │  ├─ XGBoost total prediction
      │  └─ Ensemble calculation
      │
      ├─ Store in Redis (TTL: 4 hours)
      │
      └─ Return result to user
```

### Daily Ratings Update Flow

```
User Trigger (run_today.py)
  │
  ▼
Go Ratings Sync Service
  │
  ├─ Fetch Barttorvik API
  │  └─ Get daily team efficiency ratings
  │
  ├─ Normalize team names
  │  ├─ Handle aliases
  │  └─ Match to existing teams
  │
  ├─ Store in PostgreSQL
  │  └─ Insert/update team_ratings table
  │
  └─ Signal completion
      │
      └─ Python service picks up new ratings
         └─ ML models use fresh data for next predictions
```

---

## 💾 Data Models

### PostgreSQL Tables

**teams**
```
├─ id (PK)
├─ name
├─ conference
├─ aliases (list of alternate names)
└─ created_at
```

**team_ratings**
```
├─ id (PK)
├─ team_id (FK → teams)
├─ season (year)
├─ rating_date
├─ adj_oe (offensive efficiency)
├─ adj_de (defensive efficiency)
├─ barthag (power rating)
├─ tempo (possession speed)
├─ [12+ more efficiency metrics]
└─ created_at
```

**games**
```
├─ id (PK)
├─ season
├─ home_team_id (FK → teams)
├─ away_team_id (FK → teams)
├─ game_date
├─ status (scheduled/completed)
├─ home_score
├─ away_score
├─ created_at
└─ updated_at
```

**odds_snapshots**
```
├─ id (PK)
├─ game_id (FK → games)
├─ market (spread/total)
├─ half (full/1h)
├─ line
├─ odds
├─ snapshot_time
└─ created_at
```

**predictions**
```
├─ id (PK)
├─ game_id (FK → games)
├─ market (spread/total)
├─ half (full/1h)
├─ predicted_value
├─ confidence
├─ model_version
├─ created_at
└─ created_by_user
```

---

## 🔐 Environment Configuration

### .env.local (Local Development)

Note: `.env.local` is optional for *non-secret* local overrides and is ignored by git.

For the full stack, prefer Docker Compose + secret files (see `docker-compose.yml`):

```
# Secrets are injected via files (Docker Compose mounts these at /run/secrets/*)
DB_PASSWORD_FILE=/run/secrets/db_password
REDIS_PASSWORD_FILE=/run/secrets/redis_password

# Odds API key supports either name
ODDS_API_KEY_FILE=/run/secrets/odds_api_key
THE_ODDS_API_KEY_FILE=/run/secrets/odds_api_key

# Non-secret connection details (example)
DB_HOST=postgres
DB_PORT=5432
DB_USER=ncaam
DB_NAME=ncaam
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
```

### Codespaces (Automatic)

All configured via `.devcontainer/devcontainer.json`
- No .env.local needed
- Services pre-created
- Ports auto-forwarded

---

## 🚀 Deployment Options

### Local Development
```
Your Machine
├─ PostgreSQL 15 (Windows Service)
├─ Redis (Windows Service)
└─ Python venv
    └─ FastAPI running on localhost:8000
```

### Codespaces (Development Collaboration)
```
GitHub Cloud
├─ Container with PostgreSQL 15
├─ Container with Redis 7
└─ VS Code in Browser
    └─ FastAPI can be run or tested
```

### Production (Future)
```
Azure Cloud
├─ Azure Database for PostgreSQL
├─ Azure Cache for Redis
├─ App Service (FastAPI)
└─ Container Registry (Go service)
```

---

## 🔌 API Endpoints (FastAPI)

| Endpoint | Method | Purpose | Input | Output |
|----------|--------|---------|-------|--------|
| `/health` | GET | System status | - | `{"status": "ok"}` |
| `/predict` | POST | Get prediction for game | `{game_id, market, half}` | `{prediction, confidence, model_version}` |
| `/picks` | GET | Get today's recommended picks | `?date=YYYY-MM-DD` | `{games, predictions, analysis}` |
| `/history` | GET | Prediction history | `?limit=100` | `{predictions, accuracy_stats}` |
| `/models` | GET | Model info | - | `{versions, created_at}` |
| `/docs` | GET | Interactive API docs | - | Swagger UI |

---

## 🧪 Testing Strategy

### Unit Tests
```
tests/
├─ test_models.py       # ML model loading
├─ test_predictions.py  # Prediction logic
├─ test_database.py     # DB queries
└─ test_cache.py        # Redis operations
```

### Integration Tests
```
tests/
├─ test_api.py          # Full API endpoints
├─ test_workflow.py     # End-to-end flows
└─ test_performance.py  # Load testing
```

**Run tests:**
```powershell
pytest tests/ -v
pytest tests/ --cov=services/prediction-service-python
```

---

## 📊 Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| Cache hit prediction | <1ms | Ultra-fast (in-memory) |
| DB query prediction | 50-100ms | Depends on query complexity |
| ML model inference | 10-50ms | XGBoost is fast |
| Ratings sync (full) | 30-60s | Barttorvik API + DB insert |
| Total API response | 1-200ms | Cache-dependent |

---

## 🔄 CI/CD Pipeline (Future)

```
Code Push → GitHub
  ├─ Run tests
  ├─ Check linting (ruff)
  ├─ Type check (mypy)
  └─ Build Docker images
      ├─ Python service
      └─ Go service
          │
          ▼
         Deploy to Azure
          ├─ Dev environment
          ├─ Staging
          └─ Production
```

---

## 📚 Related Documentation

- **SETUP.md** - How to set up locally
- **QUICK_START.md** - Get started in 2 minutes
- **API.md** - Detailed API documentation
- **README.md** - Project overview
- **CONTRIBUTING.md** - How to contribute

---

## 🆘 Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| API can't connect to DB | PostgreSQL not running | `Restart-Service postgresql-x64-15` |
| Slow predictions | No cache, first request | Wait 1ms for cache TTL, subsequent requests fast |
| Model loading fails | Models not found | Check `models/` directory exists with `.pkl` files |
| Ratings sync fails | Barttorvik API down | Check API status, retry manually |
| Redis connection error | Redis not running | `Restart-Service Redis` |

---

**Last Updated:** January 17, 2026
**Status:** Production Ready
