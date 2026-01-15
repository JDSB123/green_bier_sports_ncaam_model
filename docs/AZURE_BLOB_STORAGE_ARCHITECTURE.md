# Azure Blob Storage Architecture - Data Governance
**Version:** 1.0 - CANONICAL STRUCTURE  
**Date:** January 12, 2026  
**Status:** APPROVED - ENFORCEABLE

---

## 📋 Overview

This document defines the **SINGLE SOURCE OF TRUTH** for all NCAAM data storage. ALL data must reside in Azure Blob Storage with clear bifurcation between **RAW** and **CANONICAL** data.

**CRITICAL RULES:**
1. ❌ NO local data storage (except temporary processing)
2. ❌ NO data in Git repository (blocked by .gitignore)
3. ✅ ONLY Azure Blob Storage is authoritative
4. ✅ Raw and Canonical data clearly separated
5. ✅ Immutable audit trail of all transformations

---

## 🏗️ Azure Blob Storage Structure

### Storage Account: `metricstrackersgbsv`
**Resource Group:** `dashboard-gbsv-main-rg`  
**Region:** East US  
**Tier:** Hot (frequent access)

### Container 1: `ncaam-historical-raw` (RAW DATA - IMMUTABLE ARCHIVE)
**Purpose:** Original, unmodified data from all sources  
**Retention:** Permanent (immutable)  
**Access:** Read-only after initial upload  
**Size:** ~7 GB

```
ncaam-historical-raw/
├── odds_api/                           # The Odds API historical odds
│   ├── raw/
│   │   ├── 2021/
│   │   │   ├── spread_2021.json
│   │   │   ├── total_2021.json
│   │   │   └── h1_spread_2021.json
│   │   ├── 2022/
│   │   ├── 2023/
│   │   ├── 2024/
│   │   ├── 2025/
│   │   └── 2026/
│   └── import_log_odds_api.json        # Metadata: what was ingested, when
│
├── espn_api/                           # ESPN API scores
│   ├── raw/
│   │   ├── scores_2024.json
│   │   ├── scores_2025.json
│   │   └── scores_2026.json
│   ├── linescore/                      # H1 linescore data
│   │   ├── linescore_2024.json
│   │   ├── linescore_2025.json
│   │   └── linescore_2026.json
│   └── import_log_espn.json            # Metadata
│
├── barttorvik/                         # Barttorvik ratings (scraped)
│   ├── raw/
│   │   ├── ratings_2024.json
│   │   ├── ratings_2025.json
│   │   └── ratings_2026.json
│   └── import_log_barttorvik.json      # Metadata
│
├── ncaahoopR_data-master/              # R package data (box scores, stats)
│   ├── box_scores/
│   │   ├── 2024.csv                    # ~50,000 rows per season
│   │   ├── 2025.csv
│   │   └── 2026.csv
│   ├── schedule/
│   │   ├── 2024_schedule.csv
│   │   ├── 2025_schedule.csv
│   │   └── 2026_schedule.csv
│   └── import_log_ncaahoopR.json       # Metadata
│
├── basketball_api/                     # Basketball-API (when integrated)
│   ├── raw/
│   │   ├── games_2024.json
│   │   ├── games_2025.json
│   │   └── games_2026.json
│   └── import_log_basketball_api.json  # Metadata
│
├── kaggle/                             # Kaggle historical datasets
│   ├── raw/
│   │   ├── ncaa_tournament_games.csv
│   │   └── historical_march_madness.csv
│   └── import_log_kaggle.json          # Metadata
│
└── INGESTION_MANIFEST.json             # Master manifest of all raw data
    {
      "ingested_at": "2026-01-12T18:00:00Z",
      "sources": {
        "odds_api": {
          "last_import": "2026-01-12T10:00:00Z",
          "seasons": [2021, 2022, 2023, 2024, 2025, 2026],
          "blob_path": "odds_api/raw/",
          "row_count": 217151
        },
        "espn_api": {
          "last_import": "2026-01-12T08:00:00Z",
          "seasons": [2024, 2025, 2026],
          "blob_path": "espn_api/raw/",
          "row_count": 12260
        }
      }
    }
```

---

### Container 2: `ncaam-historical-data` (CANONICAL DATA - PROCESSED & TESTED)
**Purpose:** Cleaned, standardized, canonicalized data ready for backtesting  
**Retention:** Indefinite (production data)  
**Access:** Read-write (updated by ingestion pipeline only)  
**Size:** ~500 MB

```
ncaam-historical-data/
├── scores/                             # Game scores (canonicalized)
│   ├── fg/                             # Full-game scores
│   │   ├── games_all.csv               # All seasons combined (~11,763 games)
│   │   ├── games_2024.csv
│   │   ├── games_2025.csv
│   │   └── games_2026.csv
│   └── h1/                             # First-half scores (when available)
│       ├── h1_games_all.csv            # All H1 scores combined
│       ├── h1_games_2024.csv
│       ├── h1_games_2025.csv
│       └── h1_games_2026.csv
│
├── odds/                               # Betting odds (canonicalized)
│   ├── normalized/                     # SINGLE SOURCE FOR ODDS
│   │   ├── odds_consolidated_canonical.csv      # 217,151 rows
│   │   │   Columns: game_date, home_team, away_team, 
│   │   │           spread, spread_home_price, spread_away_price,
│   │   │           total, total_over_price, total_under_price,
│   │   │           h1_spread, h1_spread_home_price, h1_spread_away_price,
│   │   │           h1_total, h1_total_over_price, h1_total_under_price,
│   │   │           moneyline_home_price, moneyline_away_price,
│   │   │           source, ingested_at, data_vintage
│   │   └── odds_consolidated_canonical_summary.json
│   └── raw/archive/                    # Raw odds before canonicalization (immutable backup)
│       ├── 2021_raw_spreads.csv
│       ├── 2021_raw_totals.csv
│       ├── [... 2022, 2023, 2024, 2025, 2026 ...]
│       └── transformation_log.json
│
├── ratings/                            # Team efficiency ratings (canonicalized)
│   ├── barttorvik/                     # Primary ratings source
│   │   ├── ratings_2024.csv
│   │   ├── ratings_2025.csv
│   │   ├── ratings_2026.csv
│   │   └── ratings_index.json          # Metadata: coverage, dates
│   └── archive/
│       └── ratings_pre_standardization/ # Historical versions before standardization
│
├── backtest_datasets/                  # BACKTEST-READY DATA
│   ├── backtest_master.csv             # SINGLE SOURCE: merged scores + odds + ratings (+ optional ncaahoopR)
│   │   # 11,763 rows (all seasons)
│   │   # 87% odds coverage, 79% ratings coverage
│   │
│   ├── barttorvik_ratings.csv          # Cached ratings snapshot
│   ├── team_aliases_db.json            # MASTER: Team name resolution
│   │   # 2,361 aliases → 1,229 canonical teams
│   │   # Updated: 2026-01-12
│   │
│   └── backtest_dataset_manifest.json  # Metadata
│       {
│         "created_at": "2026-01-12T18:13:00Z",
│         "source_versions": {
│           "scores": "espn_api_2026-01-12",
│           "odds": "odds_api_consolidated_2026-01-12",
│           "ratings": "barttorvik_2026-01-12",
│           "ncaahoopR": "ncaahoopR_2026-01-10"
│         },
│         "row_counts": {
│           "total_games": 11763,
│           "with_fg_odds": 10323,
│           "with_h1_odds": 10261,
│           "with_ratings": 9389
│         },
│         "seasons": [2024, 2025, 2026],
│         "validation_status": "PASSED",
│         "audit_trail": "See comprehensive_ingestion_audit.json"
│       }
│
├── canonicalized/                      # LEGACY: Pre-2026 canonicalized data (immutable)
│   ├── scores/
│   ├── odds/
│   └── README.txt                      # Note: Superseded by /scores and /odds
│
└── DATA_GOVERNANCE_MANIFEST.json       # MASTER MANIFEST
    {
      "version": "1.0",
      "last_updated": "2026-01-12T18:14:00Z",
      "containers": {
        "ncaam-historical-raw": {
          "purpose": "Original unmodified data from all sources",
          "access": "Read-only after ingestion",
          "retention": "Permanent (immutable)",
          "sources": ["odds_api", "espn_api", "barttorvik", "ncaahoopR", "basketball_api", "kaggle"]
        },
        "ncaam-historical-data": {
          "purpose": "Cleaned, canonicalized, backtest-ready data",
          "access": "Read-write (pipeline only)",
          "retention": "Indefinite",
          "subdirectories": ["scores", "odds", "ratings", "backtest_datasets"]
        }
      },
      "data_flow": {
        "raw_data_entry": "Azure blob storage ONLY",
        "processing": "testing/canonical/ pipeline",
        "quality_gates": "testing/canonical/quality_gates.py",
        "output": "ncaam-historical-data/ (canonical)",
        "audit": "comprehensive_ingestion_audit.py"
      },
      "compliance": {
        "no_local_storage": true,
        "no_git_storage": true,
        "single_source_of_truth": "Azure blob storage",
        "audit_trail": "immutable"
      }
    }
```

---

## 🔄 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     EXTERNAL DATA SOURCES                        │
│  The Odds API | ESPN API | Barttorvik | ncaahoopR | Basketball  │
│                      | Kaggle | GitHub                           │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              AZURE BLOB STORAGE: RAW DATA                        │
│     ncaam-historical-raw/ (immutable, permanent archive)         │
│                                                                  │
│  • odds_api/raw/          [Original odds, unmodified]           │
│  • espn_api/raw/          [Original scores, unmodified]         │
│  • barttorvik/raw/        [Original ratings, unmodified]        │
│  • ncaahoopR_data-master/ [R package data, unmodified]          │
│  • basketball_api/raw/    [When integrated]                     │
│  • kaggle/raw/            [When integrated]                     │
│                                                                  │
│  + INGESTION_MANIFEST.json [Audit trail of what was ingested]  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ (Read → Transform)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│           LOCAL PROCESSING (TEMPORARY ONLY)                      │
│  testing/canonical/ingestion_pipeline.py                         │
│                                                                  │
│  1. Validate                                                     │
│  2. Canonicalize (team names via team_aliases_db.json)         │
│  3. Standardize (dates, formats)                               │
│  4. Transform (derive calculated fields)                        │
│  5. Quality Check (data integrity gates)                        │
│  6. Output → Azure (NEVER stored locally)                       │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│        AZURE BLOB STORAGE: CANONICAL DATA                        │
│    ncaam-historical-data/ (production, tested, ready)           │
│                                                                  │
│  • scores/fg/games_all.csv         [11,763 games, canonical]   │
│  • scores/h1/h1_games_all.csv      [H1 scores when available]  │
│  • odds/normalized/odds_consolidated_canonical.csv  [217,151 rows]
│  • ratings/barttorvik/ratings_*.csv [Canonicalized ratings]   │
│  • backtest_datasets/backtest_master.csv       [BACKTEST READY]│
│  • backtest_datasets/team_aliases_db.json      [2,361 aliases] │
│                                                                 │
│  + AUDIT_TRAIL.json [Complete transformation history]          │
│  + DATA_GOVERNANCE_MANIFEST.json [This structure definition]   │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ (Read → Backtest/Predict)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│               BACKTESTING / PREDICTION                           │
│  testing/scripts/run_historical_backtest.py                      │
│  testing/scripts/run_clv_backtest.py                             │
│  services/prediction-service-python/app/main.py                  │
│                                                                  │
│  Always read from: ncaam-historical-data/ (Azure)               │
│  Output: Reports + Predictions (never stored locally)           │
└─────────────────────────────────────────────────────────────────┘
```

---

## ✅ Compliance Rules

### Rule 1: Data Entry Point
```
✅ ALLOWED:  Upload to Azure blob storage via testing/azure_io.py
❌ BLOCKED:  Store data in Git
❌ BLOCKED:  Store data in local /data/ directories (except temp)
```

### Rule 2: Data Transformation
```
✅ ALLOWED:  Process in memory, output directly to Azure
✅ ALLOWED:  Temporary local files in /testing/data/tmp_* (auto-cleaned)
❌ BLOCKED:  Store processed data locally permanently
❌ BLOCKED:  Commit data to Git in any form
```

### Rule 3: Data Reading
```
✅ ALLOWED:  Read from Azure via AzureDataReader
✅ ALLOWED:  Cache in memory during execution
❌ BLOCKED:  Read from local file copies
❌ BLOCKED:  Use Git-stored data files
```

### Rule 4: Audit Trail
```
✅ REQUIRED: Log all ingestion operations
✅ REQUIRED: Record source → canonical transformation
✅ REQUIRED: Version data with ingestion timestamp
❌ NOT OK:   Delete or modify audit logs
```

---

## 📝 Versioning & Timestamps

Every file in `ncaam-historical-data/` includes:

```
Filename: odds_consolidated_canonical_2026-01-12T18-14-00Z.csv
          └──────────────────┬──────────────────┘
                    Ingestion timestamp (ISO 8601)

Columns:
  - source: "odds_api" | "basketball_api" [Where it came from]
  - ingested_at: "2026-01-12T10:00:00Z" [When it was ingested]
  - data_vintage: "2026-01-11" [What date data represents]
```

---

## 🔐 Data Retention Policy

| Container | Retention | Access | Modification |
|-----------|-----------|--------|--------------|
| `ncaam-historical-raw` | Permanent | Read-only | Immutable after upload |
| `ncaam-historical-data` | Indefinite | Read-write (pipeline) | Append-only, versioned |
| `/testing/data/tmp_*` | 7 days | Read-write | Auto-purged |
| Local `/` directories | None | N/A | BLOCKED |
| Git repository | None | N/A | BLOCKED |

---

## 🚨 Enforcement Mechanisms

### 1. .gitignore (Prevents local data leakage)
See `GITIGNORE_ENFORCEMENT.md`

### 2. Quality Gates (Prevents bad data)
```python
from testing.canonical.quality_gates import DataQualityGate

gate = DataQualityGate()
# Blocks data with nulls, invalid ranges, etc.
clean_df = gate.validate_and_raise(df, "scores")
```

### 3. Audit Trails (Immutable history)
```python
from testing.canonical.ingestion_pipeline import CanonicalIngestionPipeline

pipeline = CanonicalIngestionPipeline(enable_audit=True)
result = pipeline.ingest_scores_data(df, source="ESPN")
# Audit trail written to: manifests/audit_*.json
```

### 4. Compliance Validator (Ensures adherence)
```bash
python testing/scripts/data_governance_validator.py --strict
# Fails if finds:
#   - Local data files in /testing/data/ (not temp)
#   - Data files in Git
#   - Scripts reading from local instead of Azure
#   - Missing audit trails
```

---

## 🏁 Summary

**SINGLE SOURCE OF TRUTH:**
- ✅ All data in Azure blob storage
- ✅ Clear raw ↔ canonical separation
- ✅ Immutable audit trails
- ✅ Versioned with ingestion timestamps
- ✅ Governed by quality gates

**NO LOCAL STORAGE:**
- ❌ No permanent local data
- ❌ No data in Git
- ❌ Only temporary processing allowed
- ❌ All output → Azure immediately

**ENFORCED BY:**
- `.gitignore` (prevents accidental commits)
- `DataQualityGate` (prevents bad data)
- `CanonicalIngestionPipeline` (enforces transformation)
- `AzureDataReader` (enforces Azure-first reads)
- `data_governance_validator.py` (compliance audits)
