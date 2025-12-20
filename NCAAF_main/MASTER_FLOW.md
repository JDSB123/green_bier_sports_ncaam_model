# Master Flow - End-to-End Single Point of Entry
**Date:** December 18, 2024  
**Status:** ✅ **VERIFIED**

---

## Single Entry Point Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    EXTERNAL USER INTERFACE                      │
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────────┐  │
│  │   run.bat      │  │    run.sh      │  │  HTTP API       │  │
│  │   (Windows)    │  │   (Linux/Mac)  │  │  Port 8001      │  │
│  └───────┬────────┘  └───────┬────────┘  └────────┬────────┘  │
└──────────┼────────────────────┼─────────────────────┼──────────┘
           │                    │                     │
           └────────────────────┴─────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   DOCKER CONTAINER    │
                    │      ncaaf_v5         │
                    │  (Unified Container)  │
                    └───────────┬───────────┘
                                │
                ┌───────────────┼───────────────┐
                │               │               │
                ▼               ▼               ▼
    ┌─────────────────┐ ┌──────────────┐ ┌──────────────┐
    │   main.py       │ │ FastAPI      │ │  PostgreSQL  │
    │   (CLI Entry)   │ │ (API Entry)  │ │  (Database)  │
    └────────┬────────┘ └──────┬───────┘ └──────────────┘
             │                 │
             └────────┬────────┘
                      │
                      ▼
        ┌─────────────────────────────┐
        │   PREDICTION SERVICE        │
        │  (Single Source of Truth)   │
        │  src/services/              │
        │  prediction_service.py      │
        └──────────────┬──────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Predictor   │ │   Feature    │ │  Consensus   │
│  (Models)    │ │  Extractor   │ │   Service    │
└──────────────┘ └──────────────┘ └──────────────┘
```

---

## Entry Points

### 1. **Command Line Interface (CLI)**
**Entry:** `run.bat` (Windows) or `run.sh` (Linux/Mac)

**Flow:**
```
run.bat [command] 
  → docker compose exec ncaaf_v5 python main.py [command]
    → main.py routes to appropriate function
      → Function calls PredictionService
        → PredictionService orchestrates prediction logic
```

**Commands:**
- `run.bat predict` → Generate predictions
- `run.bat train` → Train models
- `run.bat backtest` → Run backtests
- `run.bat pipeline` → Complete pipeline
- `run.bat status` → Check system status

### 2. **HTTP API**
**Entry:** FastAPI application (Port 8001)

**Flow:**
```
GET /api/v1/predictions/week/{season}/{week}
  → FastAPI route handler
    → Calls PredictionService.generate_predictions_for_week()
      → PredictionService orchestrates prediction logic
        → Returns JSON response
```

**Key Endpoints:**
- `GET /api/v1/predictions/week/{season}/{week}` → Predictions
- `GET /api/v1/health` → Health check
- `POST /api/v1/backtests` → Create backtest

---

## Single Source of Truth

### **PredictionService** (`src/services/prediction_service.py`)

**Purpose:** THE single service that generates all predictions. Both CLI and API use this service to ensure consistency.

**Key Method:**
```python
def generate_predictions_for_week(
    self,
    season: int,
    week: int,
    save_to_db: bool = True,
    model_name: str = 'xgboost_v1'
) -> List[Dict]:
    """Generate predictions for all games in a week."""
```

**Orchestration:**
1. **Game Data Retrieval** → Fetches games from database
2. **Feature Extraction** → Uses `FeatureExtractor`
3. **Consensus Calculation** → Uses `ConsensusService`
4. **Model Prediction** → Uses `NCAAFPredictor`
5. **Recommendation Generation** → Calculates edge and recommends bets
6. **Database Persistence** → Saves predictions (optional)

**Used By:**
- ✅ `main.py` → CLI predictions (`get_picks()`)
- ✅ `src/api/main.py` → API endpoint (`get_predictions_for_week()`)
- ✅ Both ensure identical prediction logic

---

## Complete Flow Diagrams

### Prediction Flow (CLI)
```
User: run.bat predict --week 15
  ↓
run.bat: docker compose exec ncaaf_v5 python main.py predict --week 15
  ↓
main.py: get_picks(week=15, season=2025)
  ↓
main.py: prediction_service = PredictionService(db=db, model_dir='/app/models')
  ↓
main.py: predictions = prediction_service.generate_predictions_for_week(season=2025, week=15)
  ↓
PredictionService:
  1. fetch_games_by_week(season=2025, week=15)
  2. For each game:
     a. feature_extractor.extract_game_features(...)
     b. consensus_service.get_consensus(...)
     c. predictor.predict_game(features, consensus_spread, consensus_total)
     d. Calculate edge and recommendations
     e. save_prediction(...) if save_to_db=True
  3. Return list of predictions
  ↓
main.py: Format and display predictions
```

### Prediction Flow (API)
```
HTTP GET /api/v1/predictions/week/2025/15
  ↓
FastAPI: @app.get("/api/v1/predictions/week/{season}/{week}")
  ↓
FastAPI: predictions = prediction_service.generate_predictions_for_week(season=2025, week=15)
  ↓
PredictionService: [Same logic as CLI above]
  ↓
FastAPI: Return JSONResponse with predictions
```

### Training Flow
```
User: run.bat train
  ↓
run.bat: docker compose exec ncaaf_v5 python main.py train
  ↓
main.py: train_enhanced_model()
  ↓
main.py: from scripts.train_enhanced_simple import main as train_enhanced
  ↓
train_enhanced_simple.py:
  1. Load data from database
  2. Extract features
  3. Train XGBoost models
  4. Save models to /app/models/
```

### Backtesting Flow
```
User: run.bat backtest
  ↓
run.bat: docker compose exec ncaaf_v5 python main.py backtest
  ↓
main.py: run_backtest()
  ↓
main.py: backtester = EnhancedBacktester(db, start_date, end_date)
  ↓
backtest_enhanced.py:
  1. Load historical games with opening lines (no leakage)
  2. For each game:
     a. Extract features
     b. Generate predictions
     c. Evaluate bets against actual results
  3. Calculate metrics (ROI, win rate, Sharpe)
  4. Generate comparison report
```

---

## Docker-Only Execution

### Enforced Paths

**All execution MUST go through Docker:**

```bash
# ✅ CORRECT - All commands use Docker
run.bat predict    → docker compose exec ncaaf_v5 python main.py predict
run.bat train      → docker compose exec ncaaf_v5 python main.py train
run.bat backtest   → docker compose exec ncaaf_v5 python main.py backtest

# ❌ FORBIDDEN - Direct execution (will fail)
python main.py predict  # Fails: No /app path, no Docker network
go run ./cmd/worker     # Fails: Makefile prevents it
```

### Container Environment

**Unified Container (`ncaaf_v5`):**
- PostgreSQL: `localhost:5432` (internal only)
- Redis: `localhost:6379` (internal only)
- Python: Working directory `/app`
- Models: `/app/models/`
- Database: Service name `localhost` or `postgres`

**No Local Dependencies:**
- All paths assume `/app` (Docker path)
- Database connections use Docker service names
- Models loaded from Docker volume mounts

---

## Data Flow

### Prediction Data Flow
```
PostgreSQL (games, teams, odds)
  ↓
PredictionService.fetch_games_by_week()
  ↓
FeatureExtractor.extract_game_features()
  ↓
ConsensusService.get_consensus()
  ↓
NCAAFPredictor.predict_game()
  ↓
PredictionService.generate_predictions_for_week()
  ↓
PostgreSQL (save_prediction) → Optional persistence
  ↓
Return predictions (CLI or API)
```

### Training Data Flow
```
PostgreSQL (games, team_season_stats, odds)
  ↓
train_enhanced_simple.py loads historical data
  ↓
FeatureExtractor extracts features
  ↓
XGBoost training pipeline
  ↓
Models saved to /app/models/
  ↓
PredictionService loads models on next prediction
```

### Backtesting Data Flow
```
PostgreSQL (games with opening lines, predictions, actual results)
  ↓
backtest_enhanced.py.load_historical_games()
  ↓
For each game:
  - Extract features (same as prediction)
  - Generate prediction (same as PredictionService)
  - Evaluate bet against actual result
  ↓
Calculate aggregate metrics
  ↓
Generate comparison report
```

---

## Key Components

### 1. Entry Point Layer
- **`run.bat` / `run.sh`** → Docker wrapper
- **`main.py`** → Python CLI entry point
- **`src/api/main.py`** → FastAPI HTTP entry point

### 2. Service Layer (Single Source of Truth)
- **`PredictionService`** → Prediction orchestration
- **`ConsensusService`** → Market consensus calculation
- **`FeatureExtractor`** → Feature engineering

### 3. Model Layer
- **`NCAAFPredictor`** → XGBoost model predictions
- **`EnsembleNCAAFPredictor`** → Enhanced ensemble predictions
- Models stored in `/app/models/`

### 4. Data Layer
- **PostgreSQL** → Single source of truth for all data
- **Redis** → Caching layer (optional)
- **Database** → Connection management

### 5. Execution Layer
- **Docker Container** → Unified environment
- **Supervisor** → Process management (unified container)
- **Go Ingestion Service** → Data fetching (unified container)

---

## Validation Points

### ✅ Single Entry Point Verification

1. **CLI Entry:** ✅ `run.bat` → `main.py`
2. **API Entry:** ✅ FastAPI → `PredictionService`
3. **Single Source:** ✅ `PredictionService` used by both
4. **Docker Only:** ✅ All paths through Docker
5. **No Duplication:** ✅ Same logic for CLI and API

### ✅ No Bypass Paths

- ❌ Direct Python execution: Fails (wrong paths)
- ❌ Direct Go execution: Makefile prevents it
- ❌ Local scripts: All wrapped in Docker
- ✅ All operations: Docker-only

---

## Summary

**Single Point of Entry:**
- **CLI:** `run.bat` → `docker compose exec ncaaf_v5 python main.py [command]`
- **API:** HTTP requests → FastAPI → `PredictionService`

**Single Source of Truth:**
- **PredictionService** → Used by both CLI and API
- **No code duplication** → Same logic everywhere
- **Consistent results** → CLI and API produce identical predictions

**Master Flow:**
```
External → Docker → Entry Point → PredictionService → Models → Results
```

**Docker Enforcement:**
- ✅ All paths verified
- ✅ No local execution possible
- ✅ Consistent environment guaranteed

---

**Status:** ✅ **VERIFIED - Single point of entry/master flow confirmed**
