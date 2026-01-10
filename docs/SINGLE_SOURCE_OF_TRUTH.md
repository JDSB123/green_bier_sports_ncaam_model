# SINGLE SOURCE OF TRUTH - NCAAM Data & Configuration

**Last Updated:** January 10, 2026
**Document Version:** 1.0
**Application Version:** v34.0.0

---

## Version Control

### Current Release: v34.0.0

| Component | Version | Location |
|-----------|---------|----------|
| Application | 34.0.0 | `VERSION` file (root) |
| Docker Image | v34.0.0 | `ghcr.io/jdsb123/ncaam-prediction-service:v34.0.0` |
| Git Tag | v34.0.0 | `git checkout v34.0.0` |

### Versioning Strategy

- **Semantic Versioning:** `MAJOR.MINOR.PATCH`
  - MAJOR: Breaking changes to prediction logic or data schema
  - MINOR: New features, model improvements
  - PATCH: Bug fixes, documentation updates
- **Single Source:** `VERSION` file at repo root
- **Auto-propagation:** App reads from VERSION file at runtime

### Creating a New Release

```powershell
# 1. Update VERSION file
echo "34.1.0" > VERSION

# 2. Commit the change
git add VERSION
git commit -m "chore: bump version to 34.1.0"

# 3. Create annotated tag
git tag -a v34.1.0 -m "v34.1.0 - Description of changes"

# 4. Push commit and tag
git push origin main
git push origin v34.1.0
```

### Tag History

View all releases:
```powershell
git tag -l --sort=-v:refname
```

---

## Purpose

This document establishes the **canonical sources** for all NCAAM data, ensuring that any future work on this project (local, Git, Azure) references the correct, authoritative data sources.

**READ THIS FIRST** before making any changes to data ingestion, backtesting, or prediction workflows.

---

## Data Architecture Overview

```
                    SINGLE SOURCE OF TRUTH
                           |
           +---------------+---------------+
           |                               |
    [LOCAL/GIT]                      [AZURE BACKUP]
           |                               |
    ncaam_historical_data_local/     Azure Blob Storage
    (git submodule)                  metricstrackersgbsv
           |                               |
           v                               v
    backtest_master.csv              ncaam-historical-raw
    (DERIVED - rebuild on demand)    (raw data archive)
```

---

## Canonical Data Sources

### 1. Historical Data Repository (LOCAL + GIT)

**Location:** `ncaam_historical_data_local/`
**Git Remote:** `https://github.com/JDSB123/ncaam-historical-data`
**Type:** Git submodule (separate version control)

This directory contains ALL canonical historical data for the project:

| Path | Contents | Source |
|------|----------|--------|
| `scores/fg/games_all.csv` | **PRIMARY** Full-game scores (11,763 games) | ESPN |
| `scores/h1/h1_games_all.csv` | First-half scores (10,261 games) | ESPN |
| `odds/normalized/odds_consolidated_canonical.csv` | **PRIMARY** All odds data (217,151 rows) | The Odds API |
| `ratings/raw/barttorvik/` | Team efficiency ratings by season | Barttorvik |
| `backtest_datasets/team_aliases_db.json` | Team name canonicalization (1,679 aliases) | Manual |

**CRITICAL:** Never create duplicate copies of this data. Always reference these paths.

### 2. Backtest Master Dataset (DERIVED)

**Location:** `backtest_datasets/backtest_master.csv`
**Build Command:** `python testing/scripts/build_backtest_dataset.py`

This is a **derived dataset** - regenerate it from the canonical sources above.

| Metric | Coverage |
|--------|----------|
| Total Games | 11,763 |
| FG Spread | 10,323 (87.8%) |
| FG Total | 10,321 (87.7%) |
| H1 Spread | 10,261 (87.2%) |
| H1 Total | 10,261 (87.2%) |
| Ratings | 9,389 (79.8%) |

### 3. Azure Blob Storage (BACKUP)

**Storage Account:** `metricstrackersgbsv`
**Resource Group:** `dashboard-gbsv-main-rg`
**Container:** `ncaam-historical-raw`

Azure Blob Storage is a **backup** for raw data too large for GitHub:

| Blob Path | Contents | Size |
|-----------|----------|------|
| `odds/raw/archive/` | Raw API CSV files | ~210 files |
| `ncaahoopR_data-master/` | Play-by-play data | 6.7 GB |

**Sync Command:**
```powershell
python scripts/sync_raw_data_to_azure.py                    # Sync raw odds
python scripts/sync_raw_data_to_azure.py --include-ncaahoopR  # Include 6.7GB PBP
```

---

## File Reference Matrix

### For Backtesting

| Need | Use This File | NOT This |
|------|---------------|----------|
| Game scores | `scores/fg/games_all.csv` | Individual season files |
| H1 scores | `scores/h1/h1_games_all.csv` | Canonical subdirectory |
| Odds data | `odds/normalized/odds_consolidated_canonical.csv` | Raw archive files |
| Ratings | `backtest_datasets/barttorvik_ratings.csv` (cached) | Individual season files |
| Full backtest | `backtest_datasets/backtest_master.csv` | Building from scratch each time |

### For Production Predictions

| Need | Use This |
|------|----------|
| Live odds | The Odds API (via `odds-ingestion` Rust service) |
| Live ratings | Barttorvik API (via `ratings-sync` Go service) |
| Team resolution | PostgreSQL `teams` + `team_aliases` tables |

---

## Workflow: Making Data Changes

### Adding New Historical Data

1. **Add raw data** to `ncaam_historical_data_local/odds/raw/archive/` or `scores/`
2. **Rebuild canonical files** (if needed):
   ```powershell
   python testing/scripts/canonicalize_historical_odds.py
   ```
3. **Rebuild backtest master**:
   ```powershell
   python testing/scripts/build_backtest_dataset.py
   ```
4. **Validate data quality**:
   ```powershell
   python testing/scripts/score_integrity_audit.py
   python testing/scripts/dual_canonicalization_audit.py
   ```
5. **Run backtest to verify**:
   ```powershell
   python testing/scripts/run_historical_backtest.py --market fg_spread
   ```
6. **Sync to Azure** (backup):
   ```powershell
   python scripts/sync_raw_data_to_azure.py
   ```
7. **Commit to Git**:
   ```powershell
   cd ncaam_historical_data_local
   git add -A && git commit -m "Add historical data for [description]"
   git push origin main
   cd ..
   git add ncaam_historical_data_local
   git commit -m "Update historical data submodule"
   git push origin main
   ```

### Updating Team Resolution

1. **Edit aliases** in `ncaam_historical_data_local/backtest_datasets/team_aliases_db.json`
2. **Run team resolution gate**:
   ```powershell
   python testing/scripts/team_resolution_gate.py --verify
   ```
3. **Rebuild backtest master** and validate

---

## Environment Setup

### Required Environment Variables

| Variable | Purpose | Where Set |
|----------|---------|-----------|
| `AZURE_STORAGE_CONNECTION_STRING` | Azure Blob access | Local env / az CLI |
| `THE_ODDS_API_KEY` | Live odds API | `secrets/odds_api_key.txt` |
| `DB_PASSWORD` | PostgreSQL access | Docker secret |
| `REDIS_PASSWORD` | Redis access | Docker secret |

### Required Git Configuration

```powershell
# Initialize historical data submodule (first-time setup)
git submodule update --init --recursive

# Update historical data to latest
cd ncaam_historical_data_local
git pull origin main
cd ..
```

---

## CI/CD Validation Gates

The following gates run automatically on PR/push:

1. **Score Integrity Audit** - Validates score data consistency
2. **Dual Canonicalization Audit** - Verifies odds canonicalization
3. **Cross-Source Coverage Validation** - Checks team alias coverage
4. **Performance Validation** - Runs backtest, enforces:
   - ROI > -5%
   - Win Rate > 48%

See `.github/workflows/pre-backtest-validation.yml`

---

## Quick Reference Commands

```powershell
# Rebuild everything from canonical sources
python testing/scripts/build_backtest_dataset.py

# Validate data quality
python testing/scripts/score_integrity_audit.py --verbose
python testing/scripts/dual_canonicalization_audit.py --verbose

# Run backtest (all seasons)
python testing/scripts/run_historical_backtest.py --market fg_spread

# Sync to Azure backup
python scripts/sync_raw_data_to_azure.py

# Check team resolution
python testing/scripts/team_resolution_gate.py --verify

# Full audit
python testing/scripts/audit_data_sources.py
```

---

## Common Mistakes to Avoid

1. **Creating duplicate data files** - Always use canonical paths
2. **Hardcoding -110 odds** - Use actual odds from `spread_home_price`, etc.
3. **Using same-season ratings** - Use N-1 season ratings for season N games
4. **Loading individual season files** - Use `games_all.csv` as primary
5. **Skipping Azure sync** - Always backup raw data after ingestion
6. **Not rebuilding backtest_master.csv** - Regenerate after data changes

---

## Related Documentation

| Document | Purpose |
|----------|---------|
| [DATA_SOURCES.md](DATA_SOURCES.md) | Detailed data source documentation |
| [EARLY_SEASON_BETTING_GUIDANCE.md](EARLY_SEASON_BETTING_GUIDANCE.md) | 2024 anomaly analysis |
| [HISTORICAL_DATA_AVAILABILITY.md](HISTORICAL_DATA_AVAILABILITY.md) | Coverage by season |
| [CANONICAL_INGESTION_ARCHITECTURE.md](CANONICAL_INGESTION_ARCHITECTURE.md) | Ingestion pipeline |

---

## Contact

For questions about data sources or architecture, see the commit history of this repository or the related documentation files.

---

*This document is the authoritative reference for NCAAM data sources. Update this document when making architectural changes to data storage or workflows.*
