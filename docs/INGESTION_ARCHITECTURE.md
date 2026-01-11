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
│            Uses: backtest_datasets/              │
│                  team_aliases_db.json (1,679 aliases)                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    AZURE BLOB STORAGE (Canonical)                            │
│                    Container: ncaam-historical-data                          │
│  ├── scores/fg/games_all.csv           # Full-game scores                    │
│  ├── scores/h1/h1_games_all.csv        # First-half scores                   │
│  ├── odds/normalized/                  # Consolidated odds                   │
│  ├── ratings/                          # Barttorvik ratings by season        │
│  ├── backtest_datasets/                # Preprocessed data for backtests     │
│  │   └── team_aliases_db.json          # MASTER ALIAS FILE (1,679 mappings)  │
│  └── ncaahoopR_data-master/            # Box scores, PBP, schedules          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼ (Direct access)
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
| `testing/scripts/fetch_historical_data.py` | Fetch scores + Barttorvik ratings | ESPN API, Barttorvik | `scores/`, `ratings/` |
| `testing/scripts/fetch_historical_odds.py` | Fetch historical odds | The Odds API | `odds/` |
| `testing/scripts/fetch_h1_data.py` | Extract first-half scores | Azure scores + ESPN summary | `scores/h1/` |

### Team Resolution

| File | Purpose | Alias Count |
|------|---------|-------------|
| `backtest_datasets/team_aliases_db.json` | **MASTER** alias file for ingestion | 1,679 |
| PostgreSQL `team_aliases` table | Production alias table | ~950+ (sync via migrations) |
| `testing/scripts/team_resolution_gate.py` | Python gate for canonicalization | Uses JSON file |

### Backtesting Scripts

| Script | Purpose | Uses |
|--------|---------|------|
| `testing/scripts/run_historical_backtest.py` | Historical results backtest | Azure backtest_datasets |
| `testing/scripts/run_clv_backtest.py` | CLV-enhanced backtest | Azure backtest_datasets |
| `testing/scripts/build_backtest_dataset_canonical.py` | Build canonical backtest dataset | Azure scores/odds/ratings |
| `testing/scripts/build_consolidated_master.py` | Merge box-score features | Azure backtest_datasets |

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
   - Update aliases in Postgres (teams + team_aliases)
   - Export to Azure: `python scripts/export_team_registry.py --write-aliases`

2. **For production (PostgreSQL):**
   - Create migration in `database/migrations/0XX_*.sql`
   - Example: See `database/migrations/024_jan9_2026_team_aliases.sql`

---

## Repository Structure

```
NCAAM_main/
├── manifests/                       # Audit outputs & reports
├── testing/scripts/                 # Ingestion + backtest scripts
│   ├── fetch_historical_data.py     # Scores + ratings ingestion (Azure)
│   ├── fetch_historical_odds.py     # Odds ingestion (Azure)
│   ├── fetch_h1_data.py             # H1 extraction (Azure)
│   ├── team_resolution_gate.py      # Central canonicalization
│   ├── team_utils.py                # Helper wrapper
│   ├── run_historical_backtest.py   # Historical backtest engine
│   ├── run_clv_backtest.py          # CLV backtest engine
│   ├── build_backtest_dataset_canonical.py
│   └── build_consolidated_master.py
├── services/prediction-service-python/  # Production prediction service
│   └── app/main.py                  # Uses PostgreSQL for team resolution
└── database/migrations/             # PostgreSQL migrations
    └── 024_jan9_2026_team_aliases.sql  # Latest alias additions
```

---

## Quick Reference

| Question | Answer |
|----------|--------|
| Where do I add new team aliases for ingestion? | Update Postgres, then export to Azure (`scripts/export_team_registry.py --write-aliases`) |
| Where do I add new team aliases for production? | Create a database migration in `database/migrations/` |
| Which script fetches historical scores? | `testing/scripts/fetch_historical_data.py` |
| Which script fetches historical odds? | `testing/scripts/fetch_historical_odds.py` |
| Where is the master alias database? | Azure Blob `backtest_datasets/team_aliases_db.json` |
| Where is the backtest entry point? | `testing/scripts/run_historical_backtest.py` |

