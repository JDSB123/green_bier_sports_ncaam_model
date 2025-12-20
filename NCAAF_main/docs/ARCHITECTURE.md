# NCAAF v5.0 Architecture

## Overview

NCAAF v5.0 is a complete architectural redesign of the college football prediction system, following SportsDataIO's recommended data ingestion workflow and production best practices.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    SportsDataIO API                          │
│         (Teams, Games, Odds, Stats, Box Scores)              │
└─────────────────────────────────────────────────────────────┘
                            ↓ HTTP/REST
┌─────────────────────────────────────────────────────────────┐
│              Go Data Ingestion Service                       │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Background Worker (Every 60s)                       │   │
│  │  • Poll active games                                │   │
│  │  • Fetch latest odds (sharp vs public)              │   │
│  │  • Track line movement                              │   │
│  │  • Conditional fetching (only in-progress games)    │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Webhook Server (Port 8080)                         │   │
│  │  • Real-time updates from SportsDataIO              │   │
│  │  • Push-based game status changes                   │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Nightly Scheduler (2 AM daily)                     │   │
│  │  • Refresh teams, stadiums, schedules               │   │
│  │  • Static data sync                                 │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓ Write
┌─────────────────────────────────────────────────────────────┐
│                   PostgreSQL Database                        │
│  • teams, stadiums, games                                   │
│  • team_season_stats, box_scores                            │
│  • odds, line_movement                                      │
│  • predictions, bets                                        │
│  • Indexed for fast feature queries                        │
└─────────────────────────────────────────────────────────────┘
           ↓ Read                           ↑ Write
┌─────────────────────────────────────────────────────────────┐
│              Redis Cache Layer                               │
│  • Frequently accessed data (teams, odds)                   │
│  • TTL: Teams (24h), Odds (5m), Predictions (10m)           │
└─────────────────────────────────────────────────────────────┘
           ↓ Read
┌─────────────────────────────────────────────────────────────┐
│              Python ML Service (Port 8000)                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  FastAPI REST API                                   │   │
│  │  • GET /predictions/week/{season}/{week}            │   │
│  │  • GET /predictions/game/{game_id}                  │   │
│  │  • POST /models/train                               │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Feature Engineering (pandas)                       │   │
│  │  • QB rating, efficiency, talent composite          │   │
│  │  • Recent form, pace factors                        │   │
│  │  • Opponent adjustments                             │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  ML Models (XGBoost)                                │   │
│  │  • xgboost_spread.pkl (margin prediction)           │   │
│  │  • xgboost_total.pkl (total prediction)             │   │
│  │  • Trained on 2017-2022 historical data             │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Pick Generator                                     │   │
│  │  • Calculate edge vs market consensus               │   │
│  │  • Generate recommendations (spread/total/ML)       │   │
│  │  • Dynamic bet sizing (0.5-2.0 units)               │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Go Data Ingestion Service

**Purpose**: High-performance data fetching and storage

**Responsibilities**:
- **Background Worker**: Polls SportsDataIO API every 60 seconds for active games
- **Webhook Server**: Receives push notifications from SportsDataIO for real-time updates
- **Nightly Scheduler**: Refreshes static data (teams, stadiums) at 2 AM daily
- **Conditional Fetching**: Only fetches data for games that are in progress (reduces API calls)
- **Concurrent API Calls**: Fetches sharp vs public odds in parallel using goroutines
- **Database Writes**: Stores all data in PostgreSQL for local access

**Tech Stack**:
- Go 1.23+
- PostgreSQL driver (pgx/v5)
- Redis client (go-redis/v9)
- Cron scheduler (robfig/cron/v3)
- Zerolog (structured logging)

**Key Files**:
- `cmd/worker/main.go` - Background worker entry point
- `cmd/webhook/main.go` - Webhook server entry point
- `internal/client/sportsdataio.go` - SportsDataIO API client
- `internal/scheduler/scheduler.go` - Background task scheduler
- `internal/repository/` - Database access layer

### 2. PostgreSQL Database

**Purpose**: Primary data store for all game data

**Schema**:
- **teams** - Team information (245+ FBS teams)
- **stadiums** - Stadium metadata
- **games** - Game schedule and results
- **team_season_stats** - Season-level team statistics
- **odds** - Betting lines by sportsbook and market
- **line_movement** - Historical line changes
- **box_scores** - Detailed game statistics
- **predictions** - Model predictions with confidence
- **bets** - Bet tracking for CLV analysis

**Views**:
- `active_games` - Games currently in progress
- `latest_odds` - Most recent odds by game and sportsbook
- `game_results_with_predictions` - Predictions vs actual results

**Indexes**:
- `idx_games_season_week` - Fast queries by season/week
- `idx_games_status` - Filter by game status
- `idx_odds_game` - Fetch odds by game
- `idx_odds_fetched_at` - Latest odds queries

### 3. Redis Cache

**Purpose**: Fast access to frequently used data

**Cached Data**:
- **Teams**: TTL 24 hours (static data, rarely changes)
- **Odds**: TTL 5 minutes (frequently updated during games)
- **Predictions**: TTL 10 minutes (recomputed periodically)

**Keys**:
- `team:{team_id}` - Individual team data
- `odds:game:{game_id}` - Latest odds for game
- `prediction:game:{game_id}:{model}` - Cached prediction

### 4. Python ML Service

**Purpose**: Machine learning predictions and analysis

**Responsibilities**:
- **Feature Engineering**: Extract ~40-50 features from raw data
- **ML Predictions**: Run XGBoost models for spread and total predictions
- **Market Analysis**: Calculate edge vs consensus lines
- **Recommendations**: Generate betting recommendations with unit sizing
- **API**: Serve predictions via REST endpoints

**Tech Stack**:
- Python 3.12+
- FastAPI (REST API)
- XGBoost (ML models)
- pandas (data manipulation)
- scikit-learn (feature engineering)
- psycopg3 (PostgreSQL driver)
- Redis (caching)

**Key Files**:
- `src/api/main.py` - FastAPI application
- `src/features/` - Feature engineering modules
- `src/models/` - ML model wrappers
- `src/db/database.py` - Database access
- `scripts/train_xgboost.py` - Model training script
- `scripts/backtest.py` - Backtesting script

## Data Flow

### Initial Sync (First Run)

```
1. Go Worker starts
2. Fetch current season and week
3. Fetch all teams → Save to PostgreSQL
4. Fetch all stadiums → Save to PostgreSQL
5. Fetch season schedule → Save to PostgreSQL
6. Fetch team stats → Save to PostgreSQL
7. Scheduler starts background tasks
```

### Active Game Polling (Every 60s)

```
1. Query PostgreSQL for active games:
   WHERE status IN ('InProgress', 'Scheduled')
     AND game_date < NOW()
     AND status NOT IN ('Final', 'Postponed', 'Canceled')

2. For each active game:
   a. Fetch sharp odds (Pinnacle, Circa)
   b. Fetch public odds (DraftKings, FanDuel, etc.)
   c. Track line movement
   d. Update PostgreSQL

3. If EnableLineMovementTracking:
   a. Compare new odds vs previous
   b. Record line movement (direction, magnitude)
   c. Save to line_movement table
```

### Prediction Generation

```
1. Client requests: GET /predictions/week/2025/15

2. ML Service:
   a. Load games from PostgreSQL (season=2025, week=15)
   b. Load team stats from PostgreSQL
   c. Load latest odds from PostgreSQL (or Redis cache)
   d. Extract features (talent, QB, efficiency, recent form)
   e. Load XGBoost models from disk
   f. Generate predictions (spread, total, confidence)
   g. Calculate edge vs consensus
   h. Generate recommendations (if edge > threshold)
   i. Save predictions to PostgreSQL
   j. Return JSON response

3. Client receives predictions with recommended bets
```

### Nightly Refresh (2 AM Daily)

```
1. Cron triggers nightly job
2. Fetch all teams → Upsert to PostgreSQL
3. Fetch all stadiums → Upsert to PostgreSQL
4. Fetch updated season stats → Upsert to PostgreSQL
5. Clear stale Redis cache entries
```

## Design Principles

### 1. Database-First (SportsDataIO Best Practice)

- **All data stored locally** in PostgreSQL
- **Never query API on demand** - use stored data
- **Scheduled background workers** handle data fetching
- **Reduces API calls** and improves response times

### 2. Separation of Concerns

- **Go Service**: Data ingestion, storage, background tasks
- **Python Service**: ML predictions, feature engineering, API
- **PostgreSQL**: Single source of truth for all data
- **Redis**: Performance optimization layer

### 3. Conditional Fetching (SportsDataIO Best Practice)

- **Only fetch active games** (not completed/postponed/canceled)
- **Reduces API usage** by 70-90%
- **Respects rate limits** automatically
- **Avoids unnecessary API calls**

### 4. Explicit Error Handling

- **No silent fallbacks** - fail loudly and log
- **Exponential backoff** for API retries
- **Comprehensive logging** at all layers
- **Health checks** for all services

### 5. Scalability

- **Horizontal scaling**: Run multiple Go workers (load-balanced)
- **Connection pooling**: PostgreSQL and Redis pools
- **Concurrent API calls**: Goroutines for parallel fetching
- **Caching layer**: Redis reduces database load

## Deployment Architecture

### Development (Docker Compose)

```yaml
services:
  postgres:    # PostgreSQL database
  redis:       # Redis cache
  ingestion:   # Go data ingestion service
  ml_service:  # Python ML service
```

### Production (Kubernetes - Future)

```
┌─────────────────────────────────────────────┐
│  Load Balancer                              │
└─────────────────────────────────────────────┘
         ↓                    ↓
┌────────────────┐   ┌────────────────┐
│  Ingestion     │   │  ML Service    │
│  Deployment    │   │  Deployment    │
│  (3 replicas)  │   │  (2 replicas)  │
└────────────────┘   └────────────────┘
         ↓                    ↓
┌─────────────────────────────────────────────┐
│  PostgreSQL StatefulSet (with persistence)  │
└─────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────┐
│  Redis Deployment (cache layer)             │
└─────────────────────────────────────────────┘
```

## Monitoring & Observability

### Metrics (Port 9090)

- **Ingestion Service**:
  - API requests per minute
  - Active game count
  - Database write latency
  - API error rate
  - Cache hit/miss ratio

- **ML Service**:
  - Prediction requests per minute
  - Model inference time
  - Feature extraction time
  - Database query latency

### Logs (Structured JSON)

- **Zerolog** (Go): Structured JSON logs
- **Structlog** (Python): Structured JSON logs
- **Log Levels**: DEBUG, INFO, WARN, ERROR, FATAL

### Health Checks

- `GET /health` - All services
- Database connectivity check
- Redis connectivity check
- Model availability check

## Security

- **API Keys**: Stored in environment variables (never in code)
- **Database**: Password-protected, SSL optional
- **Webhooks**: Signed with secret key
- **Docker**: Non-root user in containers
- **Network**: Services communicate via private Docker network

## Performance Targets

- **API Response Time**: < 200ms (95th percentile)
- **Prediction Generation**: < 500ms per game
- **Database Queries**: < 50ms (95th percentile)
- **Background Worker**: Poll every 60s reliably
- **Uptime**: 99.9% (excluding maintenance windows)
