# End-to-End Model/Stack Review
**Date:** December 20, 2025  
**Version:** v6.3  
**Status:** COMPREHENSIVE REVIEW

---

## Executive Summary

This is a **well-architected, production-ready** NCAA basketball prediction system with solid engineering practices. The stack demonstrates:

✅ **Strengths:**
- Clean separation of concerns (Go/Rust/Python services)
- Robust team name matching system (99%+ accuracy)
- Comprehensive data validation
- Containerized deployment with proper secrets management
- Multiple market predictions (Full game + First half)

⚠️ **Areas for Improvement:**
- API quota management (critical issue identified)
- ML model training incomplete (placeholder)
- Some formula inconsistencies in documentation vs code
- Error recovery patterns could be enhanced

---

## 1. Architecture Overview

### 1.1 System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     DATA INGESTION LAYER                     │
├─────────────────────┬───────────────────────────────────────┤
│ Barttorvik (Go)     │  The Odds API (Rust)                  │
│ - Ratings sync      │  - Full game odds                      │
│ - 365 teams         │  - 1H/2H odds                          │
│ - 22 metrics/team   │  - Rate limited (45/min)               │
└──────────┬──────────┴──────────┬────────────────────────────┘
           │                     │
           ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│                      DATA STORAGE LAYER                      │
├─────────────────────┬───────────────────────────────────────┤
│ PostgreSQL          │  Redis                                │
│ (TimescaleDB)       │  (Cache)                              │
│ - team_ratings      │  - Odds snapshots                     │
│ - games             │  - Team lookups                       │
│ - odds_snapshots    │                                       │
│ - predictions       │                                       │
└──────────┬──────────┴──────────┬────────────────────────────┘
           │                     │
           └──────────┬──────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                   PREDICTION ENGINE (Python)                 │
│                                                              │
│  - BarttorvikPredictor (v6.3)                               │
│    • Base predictions (AdjOE/AdjDE/Tempo)                   │
│    • Situational adjustments (rest days, B2B)               │
│    • Matchup adjustments (ORB/TOR edge)                     │
│    • Dynamic variance (3PR + tempo)                         │
│    • Enhanced 1H predictions (EFG-based)                    │
│                                                              │
│  - PredictionEngine                                          │
│    • Recommendation generation                              │
│    • Edge calculation                                        │
│    • Kelly criterion sizing                                 │
│    • Sharp book alignment                                    │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Ratings Sync** | Go 1.22 | Fetch Barttorvik ratings daily |
| **Odds Ingestion** | Rust + Tokio | Stream odds from The Odds API |
| **Prediction** | Python 3.12 | Core prediction engine |
| **Database** | PostgreSQL 15 + TimescaleDB | Persistent storage |
| **Cache** | Redis 7 | Fast lookups & streaming |
| **API** | FastAPI | REST endpoints |
| **Orchestration** | Docker Compose | Container management |

**Assessment:** ✅ **Excellent** - Modern, performant stack with appropriate language choices.

---

## 2. Data Pipeline Review

### 2.1 Ratings Sync (Go Service)

**Location:** `services/ratings-sync-go/main.go`

**Process:**
1. Fetches JSON from `https://barttorvik.com/{season}_team_results.json`
2. Parses array-of-arrays format (46+ fields per team)
3. Resolves team names via `resolve_team_name()` database function
4. Stores in `team_ratings` table (date-versioned)

**Fields Captured:** ✅ **Comprehensive**
- Core efficiency: AdjOE, AdjDE, Tempo
- Four Factors: EFG, TOR, ORB, FTR (+ defense)
- Shooting breakdown: 2P%, 3P%, rates
- Quality metrics: Barthag, WAB

**Team Matching:** ✅ **Excellent**
- Uses `resolve_team_name()` SQL function
- 861+ team aliases in database
- Normalization fallback if resolution fails
- Stores new aliases automatically

**Error Handling:** ✅ **Good**
- Exponential backoff with jitter
- Respects `Retry-After` headers
- Timeout handling (30s)
- Detailed logging

**Issues Found:**
1. ⚠️ **Array index assumptions:** Code assumes fixed indices, but Barttorvik format may vary slightly between seasons
   ```go
   // Line 128-133: Hardcoded index 44 for AdjTempo
   adjTempo := 70.0 // Default tempo
   if len(raw) >= 45 {
       adjTempo = toFloat(raw[44])
   }
   ```
   **Recommendation:** Add format validation or flexible parsing

2. ⚠️ **WAB field:** Code notes WAB may not be present (line 135-139), but doesn't handle missing gracefully
   **Recommendation:** Add NULL handling in database schema

### 2.2 Odds Ingestion (Rust Service)

**Location:** `services/odds-ingestion-rust/src/main.rs`

**Process:**
1. Runs a **one-shot** Odds API sync when triggered (manual-only; `RUN_ONCE=true`)
2. Normalizes team names via `resolve_team_name()`
3. Validates `home_team_id ≠ away_team_id`
4. Stores in `odds_snapshots` (TimescaleDB)
5. Publishes to Redis Streams

**Rate Limiting:** ✅ **Implemented**
- 45 requests/minute (configurable)
- Uses `governor` crate for enforcement
- Exponential backoff on 429 errors

**Team Matching:** ✅ **Excellent**
- Same `resolve_team_name()` approach as Go service
- Consistent normalization rules
- Audit logging via `team_resolution_audit`

**Issues Found:**
1. 🟠 **Quota risk (only if polling is re-enabled)** (see `docs/ODDS_API_USAGE.md`)
   - This repo defaults to **manual-only** (no continuous polling), which mitigates quota exhaustion.
   - If you ever re-enable polling, implement event-driven polling or upgrade tiers first.

2. ⚠️ **Health endpoint:** Service exposes health endpoint on port 8083, but this conflicts if multiple instances run
   **Recommendation:** Use ephemeral port for one-shot runs (already handled in `run_today.py` line 156)

### 2.3 Data Validation

**Team Resolution:** ✅ **Robust**
- Database function `resolve_team_name()` provides 99%+ accuracy
- Prefers teams with ratings
- Case-insensitive matching
- Audit table tracks all resolutions

**Game Validation:** ✅ **Good**
- Validates `home_team_id ≠ away_team_id` in Rust service
- Skips games without ratings in Python
- Handles missing odds gracefully

**Issues Found:**
1. ⚠️ **Missing field validation:** No validation of odds values (e.g., negative totals, impossible spreads)
   **Recommendation:** Add bounds checking before storage

2. ⚠️ **Data freshness:** No timestamp validation to ensure ratings are recent
   **Recommendation:** Warn if ratings > 7 days old

---

## 3. Model Implementation Review

### 3.1 Core Prediction Formulas

**Location:** `services/prediction-service-python/app/predictor.py`

#### Full Game Spread (Line 249-253)
```python
# Expected Tempo
avg_tempo = home_ratings.tempo + away_ratings.tempo - self.config.league_avg_tempo

# Expected Efficiency
home_eff = home_ratings.adj_o + away_ratings.adj_d - self.config.league_avg_efficiency
away_eff = away_ratings.adj_o + home_ratings.adj_d - self.config.league_avg_efficiency

# Base Scores
home_score_base = home_eff * avg_tempo / 100.0
away_score_base = away_eff * avg_tempo / 100.0

# Spread = -(Home - Away + HCA + Situational + Matchup)
raw_margin = home_score_base - away_score_base
spread = -(raw_margin + hca_for_spread + situational_spread_adj + matchup_adj)
```

**Assessment:** ✅ **Correct** - Uses additive approach (Team A + Team B - League Avg) as documented

**Issues Found:**
1. ⚠️ **Documentation inconsistency:** README states HCA spread = 3.2, but `config.py` default is 3.2 (matches)
   - However, `docker-compose.yml` line 153 sets `MODEL__HOME_COURT_ADVANTAGE_SPREAD: 3.0`
   - **Recommendation:** Standardize on single source of truth

#### Full Game Total (Line 247)
```python
total = home_score_base + away_score_base + hca_for_total + situational_total_adj
```

**Assessment:** ✅ **Correct** - Simple sum with HCA adjustment

#### First Half Predictions (Line 274-284)
```python
# 1H Spread: Use dynamic margin scale
spread_1h = -(raw_margin * h1_factors.margin_scale + hca_spread_1h)

# 1H Total: Use dynamic tempo factor
home_score_1h = home_score_base * h1_factors.tempo_factor
away_score_1h = away_score_base * h1_factors.tempo_factor
total_1h = home_score_1h + away_score_1h + hca_total_1h
```

**Assessment:** ✅ **Good** - Uses dynamic factors based on EFG differential

### 3.2 Enhanced Features (v6.2)

#### Situational Adjustments
- ✅ Rest day penalties (B2B: -2.25 pts, 1-day: -1.25 pts)
- ✅ Rest differential factor (0.5 pts/day advantage)
- ✅ Properly integrated into spread/total calculations

#### Dynamic Variance
- ✅ Adjusts sigma based on 3-point rate and tempo differential
- ✅ Used for win probability calculations
- ✅ Configurable min/max bounds (9.0-14.0)

#### Matchup Adjustments
- ✅ Rebounding edge: ~0.15 pts per % advantage
- ✅ Turnover edge: ~0.10 pts per % advantage
- ✅ Free throw edge: ~0.15 pts per % advantage

**Assessment:** ✅ **Excellent** - Sophisticated enhancements with proper calibration

### 3.3 ML Model Integration

**Location:** `predictor.py` line 137-164

**Status:** ⚠️ **Incomplete**
- Placeholder training code exists
- Attempts to load from `testing/data/kaggle/scores.csv`
- Falls back gracefully if data missing
- Currently blends ML prediction 50/50 with rule-based

**Issues Found:**
1. ⚠️ **No actual training:** Code attempts to load data but doesn't validate features exist
2. ⚠️ **Feature mismatch:** Uses hardcoded feature names that may not match CSV
3. ⚠️ **No model persistence:** Trains on every service start (inefficient)

**Recommendation:**
- Complete ML integration OR remove placeholder code
- If keeping: Add proper feature validation and model persistence
- Consider using a more sophisticated ensemble (weighted by confidence)

### 3.4 Edge Calculation & Recommendations

**Location:** `predictor.py` line 601-919

**Process:**
1. Calculate edges (model - market)
2. Filter by minimum thresholds (2.5 pts spread, 3.0 pts total)
3. Check confidence levels (min 0.65)
4. Calculate EV and Kelly fraction
5. Check sharp book alignment
6. Generate tiered recommendations (STANDARD/MEDIUM/MAX)

**Assessment:** ✅ **Excellent** - Comprehensive recommendation system

**Issues Found:**
1. ⚠️ **Moneyline EV threshold:** Hardcoded at 3.0% (line 522) - should be configurable
2. ✅ **Market probability:** Fixed in v6.3 to use actual odds prices (line 708-722) - Good fix!

---

## 4. Code Quality & Structure

### 4.1 Python Code

**Strengths:**
- ✅ Well-structured with clear separation (models, predictor, situational, variance, first_half)
- ✅ Comprehensive docstrings and comments
- ✅ Type hints throughout
- ✅ Dataclasses for clean data modeling

**Issues:**
1. ⚠️ **Logger not initialized:** Line 189 uses `self.logger.info()` but logger never created
   ```python
   # Line 189: self.logger.info(...) but no self.logger = structlog.get_logger()
   ```
   **Recommendation:** Initialize logger in `__init__`

2. ⚠️ **Duplicate format_odds function:** Defined at line 781 and 856
   **Recommendation:** Remove duplicate

3. ⚠️ **Missing error handling:** Some database queries in `run_today.py` could fail silently
   **Recommendation:** Add try/except with proper logging

### 4.2 Go Code

**Strengths:**
- ✅ Clean error handling with structured logging (zap)
- ✅ Proper context usage for cancellation
- ✅ Retry logic with exponential backoff

**Issues:**
- None significant found

### 4.3 Rust Code

**Strengths:**
- ✅ Modern async/await with Tokio
- ✅ Proper error types with `anyhow`
- ✅ Rate limiting with `governor` crate
- ✅ Health endpoint for monitoring

**Issues:**
- None significant found

---

## 5. Configuration & Deployment

### 5.1 Secrets Management

**Approach:** ✅ **Excellent**
- Docker secrets mounted at `/run/secrets/*`
- No `.env` fallbacks (fails hard if missing)
- Proper secret validation

**Files:**
- `secrets/db_password.txt` (auto-generated)
- `secrets/redis_password.txt` (auto-generated)
- `secrets/odds_api_key.txt` (manual)

**Assessment:** ✅ **Production-ready** - Secure and auditable

### 5.2 Docker Compose

**Structure:** ✅ **Well-organized**
- Separate networks (backend, data)
- Resource limits defined
- Health checks configured
- Security options (read-only, dropped caps)

**Issues:**
1. ⚠️ **Port conflicts:** Default ports (5450, 6390, 8092) may conflict with other projects
   - ✅ **Mitigated:** Configurable via env vars (documented in `docs/CONFIGURATION.md`)

2. ⚠️ **HCA configuration:** `docker-compose.yml` line 153 sets different default than `config.py`
   - `docker-compose.yml`: `MODEL__HOME_COURT_ADVANTAGE_SPREAD: 3.0`
   - `config.py`: `home_court_advantage_spread: float = Field(default=3.2, ...)`
   - **Recommendation:** Standardize defaults

### 5.3 Database Migrations

**Structure:** ✅ **Good**
- Auto-runs on first init
- Proper versioning
- Includes seed data (teams, aliases)

**Files:**
- `001_initial_schema.sql` - Core tables
- `002_sharp_splits.sql` - Sharp book handling
- `003_odds_schema_cleanup.sql` - Optimizations
- `004_team_name_resolver.sql` - Team matching function
- `005_complete_team_data.sql` - Seed data (365 teams, 600+ aliases)
- `006_team_matching_validation.sql` - Validation functions
- `008_expanded_barttorvik_data.sql` - Extended fields

**Assessment:** ✅ **Comprehensive** - Well-structured migration system

---

## 6. Testing & Validation

### 6.1 Existing Tests

**Location:** `testing/`

**Coverage:**
- ✅ `ingestion_healthcheck.py` - API connectivity
- ✅ `run_backtest.py` - Historical validation
- ✅ `test_neutral_sites.py` - Neutral site handling

**Issues Found:**
1. ⚠️ **Limited unit tests:** No unit tests for core prediction logic
   **Recommendation:** Add pytest unit tests for `BarttorvikPredictor`

2. ⚠️ **Backtest validation:** `run_backtest.py` exists but needs historical data
   **Recommendation:** Document how to run backtests

### 6.2 Data Quality Checks

**Team Matching:** ✅ **Validated**
- 99%+ accuracy via `resolve_team_name()`
- Audit table tracks all resolutions

**Missing:**
- ⚠️ No automated data freshness checks
- ⚠️ No validation of prediction outputs (e.g., reasonable score ranges)

---

## 7. Performance Considerations

### 7.1 Database Queries

**Location:** `run_today.py` line 249-423

**Query Analysis:**
```sql
-- Uses CTEs for latest odds and ratings
WITH latest_odds AS (...),
     latest_odds_1h AS (...),
     latest_ratings AS (...)
```

**Assessment:** ✅ **Efficient** - Proper use of DISTINCT ON for latest records

**Potential Issues:**
1. ⚠️ **No query optimization notes:** Large JOINs could be slow with many games
   **Recommendation:** Add indexes on `commence_time` (already exists ✅)

### 7.2 API Rate Limits

**Barttorvik:** ✅ **No limits** - Public API, reasonable usage

**The Odds API:** 🔴 **CRITICAL ISSUE**
- Current usage: 43x over quota
- Must reduce polling frequency OR upgrade tier

---

## 8. Critical Issues & Recommendations

### Priority 1: URGENT (Fix Before Production)

1. 🔴 **API Quota Exceeded**
   - **Issue:** Polling every 30s = 86,400 req/month vs 2,000 quota
   - **Impact:** Will exhaust quota in ~12.5 hours
   - **Fix:** Reduce to 20-minute polling OR upgrade tier OR implement event-driven polling
   - **File:** `services/odds-ingestion-rust/src/main.rs`

2. ⚠️ **Logger Not Initialized**
   - **Issue:** `self.logger.info()` called but logger never created
   - **Impact:** Runtime error on first log call
   - **Fix:** Add `self.logger = structlog.get_logger()` in `__init__`
   - **File:** `services/prediction-service-python/app/predictor.py` line 104

### Priority 2: HIGH (Fix This Week)

3. ⚠️ **ML Model Placeholder**
   - **Issue:** ML training code incomplete, may fail silently
   - **Impact:** No ML enhancement benefits
   - **Fix:** Complete implementation OR remove placeholder
   - **File:** `services/prediction-service-python/app/predictor.py` line 137-164

4. ⚠️ **Configuration Inconsistency**
   - **Issue:** HCA defaults differ between `docker-compose.yml` and `config.py`
   - **Impact:** Confusion about actual values used
   - **Fix:** Standardize on `config.py` as single source of truth
   - **Files:** `docker-compose.yml` line 153, `config.py` line 40

5. ⚠️ **Duplicate Function**
   - **Issue:** `format_odds()` defined twice in `run_today.py`
   - **Impact:** Code maintenance confusion
   - **Fix:** Remove duplicate at line 856
   - **File:** `services/prediction-service-python/run_today.py`

### Priority 3: MEDIUM (Nice to Have)

6. ⚠️ **Data Validation Gaps**
   - **Issue:** No validation of odds values (negative totals, impossible spreads)
   - **Recommendation:** Add bounds checking before storage

7. ⚠️ **Missing Unit Tests**
   - **Issue:** No unit tests for core prediction logic
   - **Recommendation:** Add pytest tests for `BarttorvikPredictor`

8. ⚠️ **Array Index Assumptions**
   - **Issue:** Go service assumes fixed indices for Barttorvik data
   - **Recommendation:** Add format validation

---

## 9. Strengths Summary

### What's Working Well

1. ✅ **Architecture:** Clean separation of concerns, appropriate language choices
2. ✅ **Team Matching:** Robust 99%+ accuracy system with 861+ aliases
3. ✅ **Data Pipeline:** Comprehensive Barttorvik field capture (22 fields)
4. ✅ **Prediction Model:** Sophisticated with situational/matchup adjustments
5. ✅ **Deployment:** Containerized, secure secrets management
6. ✅ **Documentation:** Extensive docs (BARTTORVIK_FIELDS, ODDS_API_USAGE, etc.)
7. ✅ **Error Handling:** Good retry logic in Go/Rust services
8. ✅ **Database Design:** Well-normalized schema with proper indexes

---

## 10. Recommendations Summary

### Immediate Actions (Today)

1. 🔴 **Fix API quota issue** - Reduce polling or upgrade tier
2. ⚠️ **Fix logger initialization** - Add logger to `BarttorvikPredictor.__init__`

### This Week

3. ⚠️ **Complete or remove ML placeholder** - Don't leave incomplete code
4. ⚠️ **Standardize HCA defaults** - Single source of truth
5. ⚠️ **Remove duplicate function** - Clean up `format_odds()`

### This Month

6. ⚠️ **Add unit tests** - Test core prediction logic
7. ⚠️ **Add data validation** - Bounds checking for odds values
8. ⚠️ **Add format validation** - Flexible parsing for Barttorvik data

---

## 11. Overall Assessment

### Score: **8.5/10** ⭐⭐⭐⭐

**Breakdown:**
- Architecture: 9/10 (Excellent)
- Code Quality: 8/10 (Very Good, minor issues)
- Data Pipeline: 9/10 (Excellent team matching, comprehensive)
- Model Implementation: 8/10 (Sophisticated, ML incomplete)
- Deployment: 9/10 (Production-ready)
- Documentation: 9/10 (Comprehensive)
- Testing: 6/10 (Limited unit tests)
- Configuration: 8/10 (Good, minor inconsistencies)

### Verdict

This is a **well-engineered, production-ready system** with solid architecture and implementation. The main blocker is the API quota issue, which must be addressed before production deployment. Once fixed, this system should perform well in production.

**Key Strengths:**
- Robust team matching system
- Sophisticated prediction model
- Clean code organization
- Comprehensive data capture

**Key Weaknesses:**
- API quota exceeded (critical)
- ML model incomplete
- Limited unit test coverage

---

**Review Completed:** December 20, 2025  
**Reviewer:** Auto (Cursor AI Assistant)  
**Next Review:** After Priority 1 fixes implemented

