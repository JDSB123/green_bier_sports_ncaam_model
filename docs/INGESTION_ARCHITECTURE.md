# NCAAM Data Ingestion Architecture

> **Last Updated:** January 9, 2026  
> **Version:** 2.0.0 (post-cleanup)

## Overview

This document defines the **single source of truth** for all data paths in the NCAAM prediction system. Follow this guide to avoid confusion about where data comes from and where it goes.

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         HISTORICAL DATA INGESTION                            │
│                    (One-time or periodic batch updates)                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
       ┌──────────────────────────────┼──────────────────────────────┐
       ▼                              ▼                              ▼
┌──────────────┐            ┌──────────────────┐           ┌──────────────────┐
│  ESPN API    │            │   The Odds API   │           │   Barttorvik     │
│  (Scores)    │            │   (Odds Lines)   │           │   (Ratings)      │
└──────┬───────┘            └────────┬─────────┘           └────────┬─────────┘
       │                             │                              │
       ▼                             ▼                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       TEAM RESOLUTION GATE                                   │
│            testing/scripts/team_resolution_gate.py                           │
│            Uses: ncaam_historical_data_local/backtest_datasets/              │
│                  team_aliases_db.json (1,679 aliases)                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LOCAL DATA REPOSITORY (Git Submodule)                     │
│                     ncaam_historical_data_local/                             │
│  ├── scores/fg/games_all.csv           # Full-game scores                    │
│  ├── scores/h1/h1_games_all.csv        # First-half scores                   │
│  ├── odds/normalized/                  # Consolidated odds                   │
│  ├── ratings/                          # Barttorvik ratings by season        │
│  ├── backtest_datasets/                # Preprocessed data for backtests     │
│  │   └── team_aliases_db.json          # MASTER ALIAS FILE (1,679 mappings)  │
│  └── ncaahoopR_data-master/            # Box scores, PBP, schedules          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼ (Azure Blob sync)
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AZURE BLOB STORAGE                                   │
│              Container: ncaam-historical-raw                                 │
│              (Backup/archive of all historical data)                         │
└─────────────────────────────────────────────────────────────────────────────┘

================================================================================

┌─────────────────────────────────────────────────────────────────────────────┐
│                         LIVE PREDICTION PIPELINE                             │
│                        (Real-time, daily operations)                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
       ┌──────────────────────────────┼──────────────────────────────┐
       ▼                              ▼                              ▼
┌──────────────┐            ┌──────────────────┐           ┌──────────────────┐
│   ESPN API   │            │   The Odds API   │           │   Barttorvik     │
│  (Today's    │            │   (Live odds     │           │   (Current       │
│   schedule)  │            │    for today)    │           │    ratings)      │
└──────┬───────┘            └────────┬─────────┘           └────────┬─────────┘
       │                             │                              │
       ▼                             ▼                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         POSTGRESQL DATABASE                                  │
│                    resolve_team_name() function                              │
│                    Uses: team_aliases table (via migrations)                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       PREDICTION SERVICE (v33.10.0)                          │
│               services/prediction-service-python/app/main.py                 │
│               Generates predictions using DB data + fresh API data           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Scripts & Their Data Sources

### Historical Data Ingestion Scripts

| Script | Purpose | Data Source | Output Location |
|--------|---------|-------------|-----------------|
| `testing/scripts/fetch_historical_data.py` | Fetch scores + Barttorvik ratings | ESPN API, Barttorvik | `ncaam_historical_data_local/scores/`, `ratings/` |
| `testing/scripts/fetch_historical_odds.py` | Fetch historical odds | The Odds API | `ncaam_historical_data_local/odds/` |
| `testing/scripts/fetch_h1_data.py` | Extract first-half scores | Local full-game data | `ncaam_historical_data_local/scores/h1/` |

### Team Resolution

| File | Purpose | Alias Count |
|------|---------|-------------|
| `ncaam_historical_data_local/backtest_datasets/team_aliases_db.json` | **MASTER** alias file for ingestion | 1,679 |
| PostgreSQL `team_aliases` table | Production alias table | ~950+ (sync via migrations) |
| `testing/scripts/team_resolution_gate.py` | Python gate for canonicalization | Uses JSON file |

### Backtesting Scripts

| Script | Purpose | Uses |
|--------|---------|------|
| `testing/scripts/backtest_v2_rolling.py` | Rolling stats backtest (no leakage) | Local data files |
| `testing/scripts/backtest_v2_enhanced.py` | Enhanced backtest with all features | Local data files |

---

## VS Code Tasks for Data Ingestion

Run these from the VS Code task runner (`Ctrl+Shift+P` → "Run Task"):

| Task | What It Does |
|------|--------------|
| `NCAAM: Ingest All (Odds+Scores/H1)` | Full ingestion of all historical data |
| `NCAAM: Scores/Barttorvik 2019-2026` | Fetch scores and ratings only |
| `NCAAM: Odds 2021-2025 (o1-o5)` | Fetch odds for each season |
| `NCAAM: H1 from games_all` | Extract first-half data |

---

## Deleted/Deprecated Files

The following files were removed during the January 9, 2026 cleanup:

### Deleted Scripts (imported from deleted `production_parity/` folder)
- `testing/scripts/canonicalize_historical_data.py`
- `testing/scripts/canonicalize_historical_odds.py`
- `testing/scripts/market_validation.py`
- `testing/scripts/run_ml_backtest.py`
- `testing/scripts/setup_roi_data.py`
- `testing/scripts/validate_canonical_odds.py`
- `testing/scripts/validate_cross_source_coverage.py`
- `testing/scripts/audit_team_aliases.py`
- `testing/scripts/comprehensive_validation.py`
- `testing/scripts/generate_canonical_manifest.py`
- `testing/scripts/secrets_manager.py`
- `testing/scripts/validate_team_canonicalization.py`
- `testing/run_backtest_suite.py`
- `testing/backtest_readiness_check.py`
- `scripts/ingest_ncaahoopR.py`

### Deleted Documentation
- `testing/BACKTEST_WORKFLOW.md` (referenced deleted folder)
- `docs/validation/EXECUTABLE_VALIDATION_SCRIPT.md` (referenced deleted folder)

---

## Adding New Team Aliases

When team names fail to resolve:

1. **For ingestion (Python):**
   - Add to `ncaam_historical_data_local/backtest_datasets/team_aliases_db.json`
   - Push to data repo: `cd ncaam_historical_data_local && git commit -am "add aliases" && git push`

2. **For production (PostgreSQL):**
   - Create migration in `database/migrations/0XX_*.sql`
   - Example: See `database/migrations/024_jan9_2026_team_aliases.sql`

---

## Repository Structure

```
NCAAM_main/
├── ncaam_historical_data_local/     # Git submodule → ncaam-historical-data repo
│   ├── backtest_datasets/
│   │   └── team_aliases_db.json     # MASTER alias file
│   ├── odds/normalized/             # Consolidated historical odds
│   ├── ratings/                     # Barttorvik ratings by season
│   ├── scores/fg/                   # Full-game scores
│   └── scores/h1/                   # First-half scores
│
├── testing/scripts/                 # All ingestion & backtest scripts
│   ├── fetch_historical_data.py    # ✓ Scores + ratings ingestion
│   ├── fetch_historical_odds.py    # ✓ Odds ingestion
│   ├── fetch_h1_data.py            # ✓ H1 extraction
│   ├── team_resolution_gate.py     # ✓ Central canonicalization
│   ├── team_utils.py               # ✓ Helper wrapper
│   ├── backtest_v2_rolling.py      # ✓ Main backtest engine
│   └── backtest_v2_enhanced.py     # ✓ Enhanced backtest
│
├── services/prediction-service-python/  # Production prediction service
│   └── app/main.py                 # Uses PostgreSQL for team resolution
│
└── database/migrations/             # PostgreSQL migrations
    └── 024_jan9_2026_team_aliases.sql  # Latest alias additions
```

---

## Quick Reference

| Question | Answer |
|----------|--------|
| Where do I add new team aliases for ingestion? | `ncaam_historical_data_local/backtest_datasets/team_aliases_db.json` |
| Where do I add new team aliases for production? | Create a database migration in `database/migrations/` |
| Which script fetches historical scores? | `testing/scripts/fetch_historical_data.py` |
| Which script fetches historical odds? | `testing/scripts/fetch_historical_odds.py` |
| Where is the master alias database? | `ncaam_historical_data_local/backtest_datasets/team_aliases_db.json` (1,679 aliases) |
| Where is the backtest entry point? | `testing/scripts/backtest_v2_rolling.py` |
