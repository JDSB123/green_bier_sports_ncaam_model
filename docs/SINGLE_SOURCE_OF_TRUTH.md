# SINGLE SOURCE OF TRUTH - NCAAM Data & Configuration

**Last Updated:** January 10, 2026
**Document Version:** 3.0 - CANONICAL INGESTION ARCHITECTURE
**Application Version:** v34.1.0

---

## 🎯 SINGLE SOURCE OF TRUTH: Azure Blob Storage + Canonical Ingestion

**ALL historical data lives in Azure Blob Storage with canonical ingestion processing.**

### Canonical Ingestion Architecture

The new canonical ingestion framework ensures data quality and consistency:

```python
from testing.canonical.ingestion_pipeline import CanonicalIngestionPipeline
from testing.canonical.team_resolution_service import get_team_resolver
from testing.canonical.quality_gates import DataQualityGate

# All data goes through canonical processing
pipeline = CanonicalIngestionPipeline()
result = pipeline.ingest_scores_data(df, source="ESPN")

# Team names are automatically resolved
resolver = get_team_resolver()
canonical_name = resolver.resolve("cal state northridge")  # → "CSU Northridge"

# Data quality is enforced preventively
gate = DataQualityGate()
clean_df = gate.validate_and_raise(df, "scores")
```

**Key Components:**
- **Team Resolution Service**: Fuzzy matching + learning for team names
- **Canonical Ingestion Pipeline**: Preventive validation & transformation
- **Data Quality Gates**: Blocking validation before data enters system
- **Schema Evolution**: Vintage-aware data quality standards

| Container | Purpose | Size |
|-----------|---------|------|
| `ncaam-historical-data` | **Primary** - Canonical data for backtesting | ~500 MB |
| `ncaam-historical-raw` | Raw data backup (ncaahoopR, API responses) | ~7 GB |

**Storage Account:** `metricstrackersgbsv`
**Resource Group:** `dashboard-gbsv-main-rg`

### Reading Data from Azure (No Download Required)

```python
from testing.azure_data_reader import read_backtest_master, AzureDataReader

# Quick access to backtest data
df = read_backtest_master(enhanced=True)

# Full reader for any file
reader = AzureDataReader()
ratings = reader.read_json("ratings/barttorvik/ratings_2025.json")
aliases = reader.read_json("backtest_datasets/team_aliases_db.json")
```

## Version Control

### Current Release: v34.1.0

| Component | Version | Location |
|-----------|---------|----------|
| Application | 34.1.0 | `VERSION` file (root) |
| Docker Image | v34.1.0 | `ghcr.io/jdsb123/ncaam-prediction-service:v34.1.0` |
| Git Tag | v34.1.0 | `git checkout v34.1.0` |

### v34.1.0 Features
- All Barttorvik endpoints integrated (22 fields)
- ncaahoopR box score features (23,891 game-level)
- Conference strength analysis
- Enhanced backtest_master_enhanced.csv (83 columns)
- **Azure Blob Storage as single source of truth**

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
                    ┌──────────────────────────────────────┐
                    │     AZURE BLOB STORAGE               │
                    │     SINGLE SOURCE OF TRUTH           │
                    └──────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
            ┌───────▼───────┐             ┌────────▼───────┐
            │ ncaam-        │             │ ncaam-         │
            │ historical-   │             │ historical-    │
            │ data          │             │ raw            │
            │ (canonical)   │             │ (7GB backup)   │
            └───────────────┘             └────────────────┘
                    │                               │
                    ├── backtest_datasets/          ├── ncaahoopR_data-master/
                    ├── scores/fg/, h1/             ├── odds/raw/archive/
                    ├── ratings/barttorvik/         │
                    ├── odds/canonical/             │
                    └── canonicalized/              │
                                                    │
            ┌───────────────────────────────────────┘
            │
            ▼
    [LOCAL CACHE - REMOVED]
    Azure Blob Storage is the only source of truth.
```

**Key Principles:**
1. Azure is the PRIMARY source - no local cache or git data copies
2. Backtesting reads directly from Azure (no download required)
3. Large files (ncaahoopR 7GB) stay in Azure only
4. Changes are written to Azure directly by ingestion scripts

---

## Canonical Data in Azure

### Container: `ncaam-historical-data` (PRIMARY)

| Blob Path | Contents | Source |
|-----------|----------|--------|
| `scores/fg/games_all.csv` | Full-game scores (11,763 games) | ESPN |
| `scores/h1/h1_games_all.csv` | First-half scores (10,261 games) | ESPN |
| `odds/normalized/odds_consolidated_canonical.csv` | All odds data (217,151 rows) | The Odds API |
| `ratings/barttorvik/` | Team efficiency ratings by season | Barttorvik |
| `backtest_datasets/team_aliases_db.json` | Team name canonicalization (1,679 aliases) | Manual |
| `backtest_datasets/backtest_master.csv` | Merged backtest dataset | Derived |
| `backtest_datasets/backtest_master_enhanced.csv` | With advanced features | Derived |

### Container: `ncaam-historical-raw` (LARGE FILES)

| Blob Path | Contents | Size |
|-----------|----------|------|
| `odds/raw/archive/` | Raw API CSV files | ~210 files |
| `ncaahoopR_data-master/` | Play-by-play & box scores | 6.7 GB |

### Backtest Master Dataset (DERIVED)

| Metric | Coverage |
|--------|----------|
| Total Games | 11,763 |
| FG Spread | 10,323 (87.8%) |
| FG Total | 10,321 (87.7%) |
| H1 Spread | 10,261 (87.2%) |
| H1 Total | 10,261 (87.2%) |
| Ratings | 9,389 (79.8%) |

**Build:**
```powershell
python testing/scripts/build_backtest_dataset_canonical.py
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

### Adding New Historical Data (Canonical Process)

1. **Add raw data** to a staging directory (not tracked) and keep Azure as the source of truth
2. **Run canonical data validator** (PREVENTIVE):
   ```powershell
   python testing/scripts/canonical_data_validator.py --data-type scores --source local
   ```
3. **Rebuild backtest master** (with canonical pipeline):
   ```powershell
   python testing/scripts/build_backtest_dataset_canonical.py --enhanced
   ```
4. **Validate canonical data quality**:
   ```powershell
   python testing/scripts/canonical_data_validator.py --comprehensive
   ```
5. **Run backtest to verify**:
   ```powershell
   python testing/scripts/run_historical_backtest.py --market fg_spread
   ```
6. **Sync to Azure with canonicalization** (SINGLE SOURCE OF TRUTH):
   ```powershell
   python scripts/sync_raw_data_to_azure.py --canonical --canonicalize
   ```

### Updating Team Resolution

1. **Edit aliases** in the Team Registry (Postgres) and export to Azure
2. **Run team resolution service**:
   ```powershell
   python -c "from testing.canonical.team_resolution_service import get_team_resolver; resolver = get_team_resolver(); print('Team resolution service ready')"
   ```
3. **Rebuild backtest master** and sync to Azure

---

## Environment Setup

### Required Environment Variables

| Variable | Purpose | Where Set |
|----------|---------|-----------|
| `AZURE_CANONICAL_CONNECTION_STRING` | Azure Blob access (canonical data) | Local env / az CLI |
| `THE_ODDS_API_KEY` | Live odds API | `secrets/odds_api_key.txt` |
| `DB_PASSWORD` | PostgreSQL access | Docker secret |
| `REDIS_PASSWORD` | Redis access | Docker secret |

### Azure CLI Setup

```powershell
# Login to Azure (required for data access)
az login

# Verify access to storage account
az storage container list --account-name metricstrackersgbsv --output table
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
# CANONICAL INGESTION WORKFLOW

# Validate data quality (preventive)
python testing/scripts/canonical_data_validator.py --comprehensive

# Rebuild backtest dataset (canonical pipeline)
python testing/scripts/build_backtest_dataset_canonical.py --enhanced

# Run backtest (all seasons)
python testing/scripts/run_historical_backtest.py --market fg_spread

# Sync to Azure with canonicalization
python scripts/sync_raw_data_to_azure.py --canonical --canonicalize

# Test team resolution service
python -c "from testing.canonical.team_resolution_service import get_team_resolver; r = get_team_resolver(); print(r.resolve('cal state northridge'))"

# LEGACY COMMANDS (deprecated - use canonical versions above)
# python testing/scripts/build_backtest_dataset.py  # Use build_backtest_dataset_canonical.py
```

---

## Canonical Architecture Benefits

✅ **Preventive Quality**: Data issues caught at ingestion, not after backtesting
✅ **Automatic Resolution**: Team names resolved via fuzzy matching + learning
✅ **Schema Evolution**: Different quality standards for different data vintages
✅ **Single Pipeline**: All data processed consistently through canonical pipeline
✅ **Azure Integration**: Direct reading from canonical blob storage
✅ **Audit Trail**: Complete history of data transformations and validations

## Common Mistakes to Avoid

1. **Bypassing canonical pipeline** - Always use `CanonicalIngestionPipeline`
2. **Manual team name fixes** - Use `TeamResolutionService` instead
3. **Reactive validation** - Use preventive `DataQualityGate` validation
4. **Ignoring schema evolution** - Check data vintage with `SchemaEvolutionManager`
5. **Direct Azure access** - Use `AzureDataReader` with canonicalization enabled

---

## Related Documentation

| Document | Purpose |
|----------|---------|
| [DATA_SOURCES.md](DATA_SOURCES.md) | Detailed data source documentation |
| [EARLY_SEASON_BETTING_GUIDANCE.md](EARLY_SEASON_BETTING_GUIDANCE.md) | 2024 anomaly analysis |
| [HISTORICAL_DATA_AVAILABILITY.md](HISTORICAL_DATA_AVAILABILITY.md) | Coverage by season |
| [CANONICAL_INGESTION_ARCHITECTURE.md](CANONICAL_INGESTION_ARCHITECTURE.md) | Ingestion pipeline |

## Canonical Components Reference

| Component | Location | Purpose |
|-----------|----------|---------|
| TeamResolutionService | `testing/canonical/team_resolution_service.py` | Fuzzy team name matching + learning |
| CanonicalIngestionPipeline | `testing/canonical/ingestion_pipeline.py` | Orchestrates data ingestion & transformation |
| DataQualityGate | `testing/canonical/quality_gates.py` | Preventive validation gates |
| SchemaEvolutionManager | `testing/canonical/schema_evolution.py` | Vintage-aware schema handling |
| AzureDataReader | `testing/azure_data_reader.py` | Canonical Azure data access |
| CanonicalDataValidator | `testing/scripts/canonical_data_validator.py` | Preventive data validation |
| BuildBacktestCanonical | `testing/scripts/build_backtest_dataset_canonical.py` | Canonical dataset building |

---

## Contact

For questions about data sources or architecture, see the commit history of this repository or the related documentation files.

---

*This document is the authoritative reference for NCAAM data sources. Update this document when making architectural changes to data storage or workflows.*
