# NCAAM Prediction Pipeline - Validation Gates

This document describes all validation gates in the prediction pipeline that ensure data quality before predictions are generated.

## 1. Sign Convention Standard

**Rule: Spread is ALWAYS from home team perspective**
- **Negative spread** = Home team is favored (expected to win by X points)
- **Positive spread** = Away team is favored (home expected to lose by X points)

**Example:**
- Duke vs UNC at Duke: `spread = -3.5` means Duke favored by 3.5
- Duke vs UNC at Duke: `spread = +5.5` means Duke is 5.5-point underdog

**Where enforced:**
- [odds_sync.py](../services/prediction-service-python/app/odds_sync.py) - `_parse_market()` extracts `home_line` from API
- [ingestion_gate.py](../testing/scripts/ingestion_gate.py) - `_validate_spread()` validates range/convention
- Database: `odds_snapshots.home_line` always stores home perspective

---

## 2. Team Name Resolution

**Goal: All team names resolve to canonical form before entering database**

### Resolution Flow
```
┌─────────────────────────────────────────────────────────────┐
│  Raw team name from source (ESPN, Odds API, Barttorvik)     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Stage 1: Exact match (case-insensitive)                    │
│  "Duke Blue Devils" → "Duke"                                │
└─────────────────────────────────────────────────────────────┘
                              │ (if no match)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Stage 2: Normalized (remove punctuation, extra whitespace) │
│  "St. Mary's (CA)" → "Saint Mary's"                         │
└─────────────────────────────────────────────────────────────┘
                              │ (if no match)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Stage 3: Aggressive (remove mascot suffix)                 │
│  "Ohio State Buckeyes" → "Ohio State"                       │
└─────────────────────────────────────────────────────────────┘
                              │ (if still no match)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  FAIL: Skip event + log to team_resolution_audit            │
└─────────────────────────────────────────────────────────────┘
```

### Alias Sources
| Source | Location | Aliases Count |
|--------|----------|---------------|
| Primary JSON | Azure Blob `backtest_datasets/team_aliases_db.json` | 1,706 |
| PostgreSQL | `team_aliases` table + `resolve_team_name()` function | 950+ |
| Legacy dict | `odds_sync.py` → `TEAM_NAME_ALIASES` | ~90 (redundant) |

### Audit Table
```sql
-- All resolution attempts logged for monitoring
SELECT * FROM team_resolution_audit 
WHERE resolved_name IS NULL 
ORDER BY created_at DESC;
```

---

## 3. Timezone Standardization

**Standard: All times in Central Time (CST/CDT)**

### Implementation
```python
from zoneinfo import ZoneInfo
CST = ZoneInfo("America/Chicago")

# UTC to CST conversion
cst_time = utc_time.astimezone(CST)
game_date = cst_time.date()  # Date in CST, not UTC
```

### Where Enforced
- [run_today.py](../services/prediction-service-python/run_today.py): Line 122 - `CST = ZoneInfo("America/Chicago")`
- [ingestion_gate.py](../testing/scripts/ingestion_gate.py): `_validate_commence_time()` converts to CST
- [validation_gate.py](../services/prediction-service-python/app/validation_gate.py): `_validate_game_time()` converts to CST

### Date Assignment Rules
Games starting after midnight UTC but before midnight CST belong to the **previous day's slate**:
- Game at `2025-01-10T02:00:00Z` (10pm EST) → CST date: `2025-01-09`

---

## 4. Data Freshness Gates

### Odds Freshness (HARD GATE - No Bypass)
```python
# From run_today.py args
max_odds_age_minutes_full = 45  # Full game spreads/totals
max_odds_age_minutes_1h = 30    # First half markets
```

**Enforced by:** `_enforce_odds_freshness_and_completeness()`

If odds are stale, the pipeline **fails** with exit code 2.

### Complete Pricing (HARD GATE)
Every market must have complete pricing:
- Spread: requires `home_line`, `home_price`, `away_price`
- Total: requires `total_line`, `over_price`, `under_price`

---

## 5. Data Quality Thresholds

### Configurable via CLI args
```bash
python run_today.py \
  --min-ratings-pct 0.85 \
  --min-odds-pct 0.70 \
  --min-1h-odds-pct 0.50
```

### Default Thresholds
| Metric | Default | Description |
|--------|---------|-------------|
| `min_ratings_pct` | 0.85 | % of games with ratings from both teams |
| `min_odds_pct` | 0.70 | % of games with at least spread or total |
| `min_1h_odds_pct` | 0.00 | % of games with 1H markets (optional) |

### Bypass Flag
`--allow-data-degrade` allows running with warnings instead of failure.

---

## 6. Team Resolution Gate (Run Today)

### Pre-Run Check
```python
tm_recent = _check_recent_team_resolution(
    engine=engine,
    lookback_days=7,
    min_resolution_rate=0.95,
)
```

### What It Checks
- Resolution rate in last N days from `team_resolution_audit`
- If any **unresolved** teams exist → Warning (not blocking)
- Detailed breakdown by source (odds_api, espn, etc.)

### Full Validator Report
```python
validator = TeamMatchingValidator()
validator.run_all_validations()
```

Runs comprehensive team matching checks across all data sources.

---

## 7. Season Year Calculation

**Rule: Games after August belong to NEXT year's season**

```python
def get_season_year(game_date: date) -> int:
    if game_date.month >= 8:  # Aug-Dec
        return game_date.year + 1
    else:  # Jan-Jul
        return game_date.year
```

**Examples:**
- `2024-11-15` → 2025 season
- `2025-01-15` → 2025 season  
- `2025-03-20` → 2025 season (March Madness)

---

## 8. Ingestion Gate (Batch Validation)

For validating historical/batch data before ingestion:

```python
from testing.scripts.ingestion_gate import IngestionGate

gate = IngestionGate()

# Validate historical game
result = gate.validate_historical_game({
    "game_date": "2024-03-15",
    "home_team": "Duke Blue Devils",
    "away_team": "UNC",
    "home_score": 78,
    "away_score": 72,
    "spread": -3.5,
})

if not result.is_valid:
    for error in result.errors:
        print(error)
```

---

## 9. Pre-Prediction Gate (Real-Time Validation)

For validating live games before prediction:

```python
from app.validation_gate import PrePredictionGate

gate = PrePredictionGate()

result = gate.validate_game({
    "home_team": "Ohio State",
    "away_team": "Nebraska",
    "commence_time": "2026-01-09T23:30:00Z",
    "spread": -8.5,
    "total": 145.5,
})

if not result.is_valid:
    print(f"Skipping game: {result.errors}")
```

---

## Validation Summary

| Gate | Type | Bypass? | Exit Code |
|------|------|---------|-----------|
| Team Resolution | Pre-run audit | Warn only | - |
| Odds Freshness | Per-game | No | 2 |
| Complete Pricing | Per-market | No | 2 |
| Data Quality | Slate-wide | `--allow-data-degrade` | 2 |
| Ratings Coverage | Slate-wide | `--allow-data-degrade` | 2 |

---

## Files Reference

| File | Purpose |
|------|---------|
| `services/prediction-service-python/run_today.py` | Main pipeline with gates |
| `services/prediction-service-python/app/odds_sync.py` | Odds ingestion with team resolution |
| `services/prediction-service-python/app/validation_gate.py` | Pre-prediction validation |
| `services/prediction-service-python/validate_team_matching.py` | Full team matching validator |
| `testing/scripts/ingestion_gate.py` | Batch data validation |
| Azure Blob `backtest_datasets/team_aliases_db.json` | Alias database |
