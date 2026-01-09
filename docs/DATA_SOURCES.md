# NCAAM Data Sources - Single Source of Truth

**Last Updated:** January 9, 2026
**Version:** 1.0

---

## Overview

This document establishes the **canonical data sources** for all NCAAM prediction and backtesting work.

**CRITICAL:** Always use the designated single source of truth to avoid data inconsistencies.

---

## Azure Blob Storage - Raw Data Archive

**Storage Account:** `metricstrackersgbsv`
**Container:** `ncaam-historical-raw`
**Resource Group:** `dashboard-gbsv-main-rg`

Azure Blob Storage serves as the **permanent archive** for all raw historical data. This includes:
- Raw odds API responses
- ncaahoopR play-by-play data
- Original Barttorvik scrapes

**Sync Script:** `scripts/sync_raw_data_to_azure.py`

---

## Canonical Data Files (Git Repository)

The following files in the Git repository are the **processed, canonical versions** of the data used for backtesting and production.

### Master Odds File (SINGLE SOURCE OF TRUTH)

**File:** `ncaam_historical_data_local/odds/normalized/odds_consolidated_canonical.csv`

This is the **only file** you should use for odds data. It contains:
- 217,151 rows (27,623 unique games)
- Date range: 2020-11-25 to 2026-01-07
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

### Scores Files

| File | Games | Description |
|------|------:|-------------|
| `canonicalized/scores/fg/games_all_canonical.csv` | 7,197 | Full-game scores |
| `canonicalized/scores/h1/h1_games_all_canonical.csv` | 7,221 | First-half scores |

### Barttorvik Ratings

**File:** `backtest_datasets/barttorvik_ratings.csv`

| Seasons | Teams | Note |
|---------|------:|------|
| 2024, 2025 | 726 | **NEEDS EXPANSION** to 2021-2023 |

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
`ncaam_historical_data_local/DATA_MANIFEST.json`

---

## Related Documentation

- [HISTORICAL_DATA_AVAILABILITY.md](HISTORICAL_DATA_AVAILABILITY.md) - Coverage by season
- [HISTORICAL_DATA_SYNC.md](HISTORICAL_DATA_SYNC.md) - Azure sync procedures
- [CANONICAL_INGESTION_ARCHITECTURE.md](CANONICAL_INGESTION_ARCHITECTURE.md) - Ingestion pipeline

---

## Backtest Scripts

| Script | Purpose |
|--------|---------|
| `testing/scripts/backtest_all_markets.py` | **Master backtest** - All 6 markets with ACTUAL prices |
| `testing/scripts/fetch_historical_odds.py` | Fetch odds from The Odds API |
| `testing/scripts/canonicalize_historical_odds.py` | Process raw odds into canonical format |
| `scripts/sync_raw_data_to_azure.py` | Sync local data to Azure |
