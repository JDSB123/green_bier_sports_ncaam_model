# Phase 2: Data Repository Plan

## Overview

Phase 2 will generate canonical data files and rolling stats cache.  
These outputs will be committed to **ncaam-historical-data** repository (NOT NCAAM_main).

---

## Why Separate Repository?

### NCAAM_main (Code Repository)
**Purpose:** Service code, ML pipelines, framework  
**Contains:**
- Python services (canonical_ingestion.py, feature_extractor.py)
- Docker configurations
- Deployment scripts
- Documentation

**What stays here:**
- Framework code (Phase 1) ✅ Committed
- Data loaders (Phase 2) - Code only
- BacktestEngine updates (Phase 3) - Code only
- Model training scripts (Phase 4) - Code only

### ncaam-historical-data (Data Repository)
**Purpose:** Historical datasets, canonical CSVs, pre-computed caches  
**Contains:**
- Raw data (Odds API, ESPN, Barttorvik, ncaahoopR)
- Canonical CSV files (game_canonical.csv, odds_canonical.csv, etc.)
- Rolling stats cache (pre-computed .pkl files)
- Backtest datasets

**What goes there:**
- Canonical CSV exports (Phase 2) ⏳ Pending
- Rolling stats cache (Phase 2) ⏳ Pending
- Data validation reports (Phase 2) ⏳ Pending

---

## Phase 2 Data Files (Will Go to ncaam-historical-data)

### Canonical CSV Files
```
ncaam-historical-data/
├── canonicalized/
│   ├── games_canonical.csv           ← All games with season-aware dates
│   │   Columns: game_id, season, date, home_team, away_team, ...
│   │   Rows: ~7,197 games (all seasons)
│   │
│   ├── odds_canonical.csv            ← All odds lines (4 markets)
│   │   Columns: game_id, source, market, spread, total, ...
│   │   Rows: ~423,000+ lines
│   │
│   ├── scores_canonical.csv          ← Final scores
│   │   Columns: game_id, final_score_home, final_score_away, ...
│   │   Rows: ~7,197 games
│   │
│   └── ratings_canonical.csv         ← Barttorvik ratings
│       Columns: team, season, adj_o, adj_d, ...
│       Rows: ~7,368 team-seasons (300+ teams × 24 seasons)
```

### Rolling Stats Cache
```
ncaam-historical-data/
├── rolling_stats_cache/
│   ├── 2024_rolling_stats.pkl        ← Pre-computed rolling stats for 2024
│   │   Size: ~2.2 GB
│   │   Contains: 5-game, 10-game, season-to-date stats for all teams
│   │
│   ├── 2025_rolling_stats.pkl        ← Pre-computed rolling stats for 2025
│   │   Size: ~85 MB (partial season)
│   │
│   └── metadata.json                 ← Cache version info
│       {
│         "version": "v34.0.0-alpha.2",
│         "created": "2025-01-13",
│         "seasons": [2024, 2025],
│         "window_sizes": [5, 10, "season"]
│       }
```

### Data Validation Reports
```
ncaam-historical-data/
├── validation_reports/
│   ├── phase2_validation_2025_01_13.md    ← Data quality report
│   │   - Team name matching: 98.7%
│   │   - Season assignment: 100%
│   │   - Data completeness: No gaps
│   │
│   └── canonical_data_summary.csv         ← Summary statistics
│       Columns: source, rows, date_range, teams_covered
```

---

## Phase 2 Git Workflow (When Ready)

### Step 1: Implement Data Loaders in NCAAM_main
```bash
cd C:\Users\JB\green-bier-ventures\NCAAM_main

git checkout -b feat/data-loaders-v34-phase2

# Implement data_loaders.py
# ... coding ...

git add testing/production_parity/data_loaders.py
git add testing/production_parity/data_validation.py
git commit -m "feat: Data loaders for all 8 sources (Phase 2)"
git push origin feat/data-loaders-v34-phase2

# Tag code
git tag -a v34.0.0-alpha.2 -m "Data loaders complete (Phase 2 - Code)"
git push origin v34.0.0-alpha.2
```

### Step 2: Run Data Loaders to Generate Outputs
```bash
# Run canonical ingestion
python testing/production_parity/data_loaders.py \
  --output-dir ../ncaam-historical-data/canonicalized \
  --cache-dir ../ncaam-historical-data/rolling_stats_cache

# This generates:
# - games_canonical.csv (7,197 games)
# - odds_canonical.csv (423,000+ lines)
# - scores_canonical.csv (7,197 games)
# - ratings_canonical.csv (7,368 team-seasons)
# - rolling_stats_cache/*.pkl (2.3 GB total)
```

### Step 3: Commit Data to ncaam-historical-data
```bash
cd C:\Users\JB\[path-to-ncaam-historical-data-repo]

# Verify repo
git remote -v
# Should show: JDSB123/ncaam-historical-data

git checkout -b data/canonical-phase2

# Add canonical CSV files
git add canonicalized/games_canonical.csv
git add canonicalized/odds_canonical.csv
git add canonicalized/scores_canonical.csv
git add canonicalized/ratings_canonical.csv

# Add rolling stats cache
git add rolling_stats_cache/2024_rolling_stats.pkl
git add rolling_stats_cache/2025_rolling_stats.pkl
git add rolling_stats_cache/metadata.json

# Add validation reports
git add validation_reports/phase2_validation_2025_01_13.md
git add validation_reports/canonical_data_summary.csv

# Commit with cross-repo reference
git commit -m "data: Canonical cache Phase 2 (v2025.01.13-phase2)

Generated by: NCAAM_main v34.0.0-alpha.2
Framework: canonical_ingestion.py + data_loaders.py

Files Added:
- games_canonical.csv: 7,197 rows (all games)
- odds_canonical.csv: 423,456 rows (all odds lines)
- scores_canonical.csv: 7,197 rows (final scores)
- ratings_canonical.csv: 7,368 rows (team-season ratings)
- rolling_stats_cache: 2.3 GB (pre-computed)

Validation:
- Team name matching: 98.7%
- Season assignment: 100% (NCAA rule)
- Data completeness: No gaps

Cross-repo references:
- Code: https://github.com/green-bier-ventures/NCAAM_main/releases/tag/v34.0.0-alpha.2
- Framework: https://github.com/green-bier-ventures/NCAAM_main/releases/tag/v34.0.0-alpha.1

Next Phase: BacktestEngine integration (v34.0.0-beta.1)
"

# Push to GitHub
git push origin data/canonical-phase2

# Tag with data-specific version
git tag -a DATA_PREP-v2025.01.13-phase2 \
  -m "Data Preparation Phase 2 Complete

Canonical data cache exported and validated.
Coordinates with: v34.0.0-alpha.2 (NCAAM_main)

Files: 4 CSV files + rolling stats cache (2.3 GB)
Quality: 98.7% team matching, 100% season correctness

Generated: January 13, 2026
"

git push origin DATA_PREP-v2025.01.13-phase2
```

---

## Repository Separation Benefits

### 1. Clean Code vs Data Separation
- **Code changes:** Version control tracks logic changes
- **Data changes:** Version control tracks dataset updates
- **Benefit:** Can update data without changing code version

### 2. Size Management
- **NCAAM_main:** Lightweight (code only, ~10 MB)
- **ncaam-historical-data:** Large (data files, ~10 GB)
- **Benefit:** Fast code repo cloning, data repo optional

### 3. Independent Versioning
- **Code:** SemVer (v34.0.0-alpha.1, v34.0.0-alpha.2, etc.)
- **Data:** Date-based (DATA_PREP-v2025.01.13-phase2)
- **Benefit:** Reprocess historical data without code changes

### 4. Clear Dependencies
- **Phase 2 code:** Committed to NCAAM_main (v34.0.0-alpha.2)
- **Phase 2 data:** Committed to ncaam-historical-data (DATA_PREP-v2025.01.13-phase2)
- **Benefit:** Explicit coordination via tags and commit messages

### 5. No Prediction Contamination
- **Prediction service:** Lives in services/prediction-service-python
- **Framework code:** Lives in testing/production_parity
- **Data outputs:** Lives in separate repo (ncaam-historical-data)
- **Benefit:** Production code stays clean, framework isolated

---

## What NOT to Commit to ncaam-historical-data

❌ **Don't commit:**
- Python code (canonical_ingestion.py, feature_extractor.py)
- Docker configurations
- Deployment scripts
- Service code (prediction-service-python)

✅ **Only commit:**
- CSV files (canonical data)
- Cache files (.pkl, .parquet)
- Validation reports
- Data documentation

---

## Current Status

### Phase 1 ✅ Complete
**Repository:** NCAAM_main  
**Branch:** feat/canonical-ingestion-v34-phase1  
**Tag:** v34.0.0-alpha.1  
**Date:** January 9, 2026  

**Committed:**
- canonical_ingestion.py (24.1 KB)
- feature_extractor.py (25.3 KB)
- 9 documentation files (127.7 KB)
- VERSION: 34.0.0

**Location:**
- GitHub: https://github.com/JDSB123/green_bier_sports_ncaam_model/tree/feat/canonical-ingestion-v34-phase1
- Tag: https://github.com/JDSB123/green_bier_sports_ncaam_model/releases/tag/v34.0.0-alpha.1

### Phase 2 ⏳ Pending
**Timeline:** Week of January 13, 2026  
**Repository (Code):** NCAAM_main → v34.0.0-alpha.2  
**Repository (Data):** ncaam-historical-data → DATA_PREP-v2025.01.13-phase2  

**To Do:**
1. Implement data_loaders.py (NCAAM_main)
2. Run canonical ingestion on all 8 sources
3. Generate canonical CSV files
4. Pre-compute rolling stats cache
5. Commit code to NCAAM_main
6. Commit data to ncaam-historical-data
7. Tag both repos with cross-references

### Phase 3 ⏳ Pending
**Timeline:** Week of January 20, 2026  
**Repository:** NCAAM_main → v34.0.0-beta.1  

**To Do:**
1. Update BacktestEngine to use rolling stats
2. Run backtests (v33 vs v34)
3. Validate accuracy improvement
4. Tag v34.0.0-beta.1

### Phase 4 ⏳ Pending
**Timeline:** Week of January 27, 2026  
**Repository:** green_bier_sports_ncaam_model → v34.0.0  

**To Do:**
1. Train model on v34 features
2. Deploy to production
3. A/B test with v33.15.0
4. Tag v34.0.0 (production)

---

## Summary

✅ **Phase 1 (Framework) - NCAAM_main**
- Code committed: feat/canonical-ingestion-v34-phase1
- Tag: v34.0.0-alpha.1
- Date: January 9, 2026
- Status: Complete

⏳ **Phase 2 (Data) - ncaam-historical-data**
- Data will be committed: data/canonical-phase2
- Tag: DATA_PREP-v2025.01.13-phase2
- Expected: January 13, 2026
- Status: Pending (framework ready, loaders next)

🎯 **Key Principle:**
- **Code** → NCAAM_main (SemVer tags)
- **Data** → ncaam-historical-data (Date-based tags)
- **Models** → green_bier_sports_ncaam_model (Release tags)

This keeps repositories clean, dependencies clear, and production code uncontaminated.
