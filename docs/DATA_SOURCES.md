# NCAAM Data Sources - Single Source of Truth

**Last Updated:** January 10, 2026
**Version:** 3.0

---

## 🎯 SINGLE SOURCE OF TRUTH: Azure Blob Storage

**ALL historical data lives in Azure Blob Storage.** No local downloads required.

**Canonical Window:** 2023-24 season onward (season 2024+). Pre-2023 data is out of scope.

| Container | Purpose | Size |
|-----------|---------|------|
| `ncaam-historical-data` | **Primary** - Canonical data for backtesting | ~500 MB |
| `ncaam-historical-raw` | Raw data backup (ncaahoopR, API responses) | ~7 GB |

**Storage Account:** `metricstrackersgbsv`
**Resource Group:** `dashboard-gbsv-main-rg`

---

## Reading Data from Azure

```python
from testing.azure_data_reader import read_backtest_master, AzureDataReader

# Quick access to backtest data
df = read_backtest_master()

# Read any file
reader = AzureDataReader()
ratings = reader.read_json("ratings/barttorvik/ratings_2025.json")
aliases = reader.read_json("backtest_datasets/team_aliases_db.json")

# Stream large ncaahoopR files
reader_raw = AzureDataReader(container_name="ncaam-historical-raw")
for chunk in reader_raw.read_csv_chunks("ncaahoopR_data-master/box_scores/2025.csv"):
    process(chunk)
```

---

## Canonical Data Files (in Azure)

### Master Odds File (SINGLE SOURCE OF TRUTH)

**File:** `odds/normalized/odds_consolidated_canonical.csv` (Azure blob path)

This is the **only file** you should use for odds data. It contains:
- 217,151 rows (27,623 unique games)
- Date range: 2023-11-01 onward (see metadata)
- ALL markets with **ACTUAL prices** (not hardcoded -110)

**Key Columns:**
| Column | Description |
|--------|-------------|
| `spread` | FG spread line |
| `spread_home_price` | **ACTUAL** spread home odds (e.g., -106, -115) |
| `spread_away_price` | **ACTUAL** spread away odds |
| `total` | FG total line |
| `total_over_price` | **ACTUAL** over odds |
| `total_under_price` | **ACTUAL** under odds |
| `moneyline_home_price` | FG moneyline home (e.g., +245, -294) |
| `moneyline_away_price` | FG moneyline away |
| `h1_spread` | First-half spread line |
| `h1_spread_home_price` | **ACTUAL** H1 spread odds |
| `h1_spread_away_price` | **ACTUAL** H1 spread odds |
| `h1_total` | First-half total line |
| `h1_total_over_price` | **ACTUAL** H1 over odds |
| `h1_total_under_price` | **ACTUAL** H1 under odds |
| `h1_moneyline_home_price` | H1 moneyline home (NOT AVAILABLE - derive from H1 spread) |
| `h1_moneyline_away_price` | H1 moneyline away (NOT AVAILABLE - derive from H1 spread) |

Note: canonical odds are filtered to pregame snapshots only. The latest snapshot at or before commence_time is retained per event to prevent leakage.

### Scores Files

| File | Games | Description |
|------|------:|-------------|
| `scores/fg/games_all.csv` | 11,763 | Full-game scores (PRIMARY) |
| `canonicalized/scores/fg/games_all_canonical.csv` | 7,197 | Legacy (do not use) |
| `canonicalized/scores/h1/h1_games_all_canonical.csv` | 7,221 | Legacy (do not use) |

### Backtest Master (SINGLE SOURCE FOR BACKTESTING)

**File:** `backtest_datasets/backtest_master.csv`

| Metric | Coverage | Note |
|--------|---------|------|
| Total Games | 11,763 | 2023-11-06 to 2025-04-08 |
| FG Spread | 10,323 (87.8%) | With actual prices |
| FG Total | 10,321 (87.7%) | With actual prices |
| H1 Spread | 10,261 (87.2%) | With actual prices |
| H1 Total | 10,261 (87.2%) | With actual prices |
| Ratings | 9,389 (79.8%) | Barttorvik |

**Build Command:** `python testing/scripts/build_backtest_dataset_canonical.py`

### Barttorvik Ratings

**File:** `backtest_datasets/barttorvik_ratings.csv` (cached)

| Seasons | Teams | Note |
|---------|------:|------|
| 2024, 2025, 2026 | ~1,089 | Auto-fetched during build |

---

## Critical Rules

### 1. NEVER Hardcode -110 Odds

```python
# WRONG - Never do this
roi = calculate_roi(bets, odds=-110)

# CORRECT - Use actual odds from data
roi = calculate_roi(bets, odds=row['spread_home_price'])
```

### 2. Use Season N-1 Ratings for Season N Games (Anti-Leakage)

```python
# WRONG - Uses same-season ratings (leakage)
ratings = get_ratings(team, season=game_season)

# CORRECT - Uses prior season ratings
ratings = get_ratings(team, season=game_season - 1)
```

### 3. H1 Models are INDEPENDENT of FG Models

```python
# WRONG - H1 is NOT FG/2
h1_spread_pred = fg_spread_pred / 2

# CORRECT - Independent H1 calculation
h1_spread_pred = calculate_h1_spread(home_ratings, away_ratings, HCA_H1=1.8)
```

### 4. Moneyline Must Align with Spread Direction

```python
# Consistency check - spread and ML must agree
if spread_pred < 0:  # Home favored
    assert ml_home_prob > 0.5, "Spread/ML mismatch!"
```

---

## Data Manifest

For a complete inventory of available data, see:
`DATA_MANIFEST.json` (Azure blob path)

---

## Related Documentation

- [HISTORICAL_DATA_AVAILABILITY.md](HISTORICAL_DATA_AVAILABILITY.md) - Coverage by season
- [HISTORICAL_DATA_SYNC.md](HISTORICAL_DATA_SYNC.md) - Azure sync procedures
- [CANONICAL_INGESTION_ARCHITECTURE.md](CANONICAL_INGESTION_ARCHITECTURE.md) - Ingestion pipeline

---

## Backtest Scripts

| Script | Purpose |
|--------|---------|
| `testing/scripts/build_backtest_dataset_canonical.py` | **Build master dataset** - Merges scores, odds, ratings |
| `testing/scripts/run_historical_backtest.py` | **Run backtests** - Against actual outcomes |
| `testing/scripts/backtest_all_markets.py` | Legacy backtest - All 6 markets with ACTUAL prices |
| `testing/scripts/audit_data_sources.py` | Quick data availability audit |
| `scripts/sync_raw_data_to_azure.py` | Sync staged data to Azure |

## Data Workflow

```
1. Raw Data ingested/updated in a staging directory (not tracked)
                |
                v
2. sync_raw_data_to_azure.py uploads to Azure (SINGLE SOURCE OF TRUTH)
                |
                v
3. build_backtest_dataset_canonical.py creates backtest_master.csv
                |
                v
4. run_historical_backtest.py reads from Azure, runs backtests
                |
                v
5. CI/CD validates ROI > -5%, Win Rate > 48%
```

## Sync Local to Azure

```powershell
# Sync canonical data (scores, odds, ratings, backtest datasets)
python scripts/sync_raw_data_to_azure.py --canonical

# Sync everything including ncaahoopR (7GB)
python scripts/sync_raw_data_to_azure.py --all --include-ncaahoopR

# Preview what would sync
python scripts/sync_raw_data_to_azure.py --all --dry-run
```
