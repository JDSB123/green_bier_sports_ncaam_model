**Canonical window:** 2023-24 season onward (season 2024+). Pre-2023 data is out of scope.
<!-- Purpose: document current historical coverage, season rules, gaps, and how to fetch missing data. -->
# Historical Data Coverage, Season Rules, and Gaps

## Data Source of Truth

All historical data lives in Azure Blob Storage: `metricstrackersgbsv/ncaam-historical-data`.

Canonical layout (Azure Blob):
```
ncaam-historical-data/
|-- scores/
|   |-- fg/           # Full-game scores: games_YYYY.csv, games_all.csv
|   `-- h1/           # First-half scores: h1_games_all.csv
|-- odds/
|   |-- raw/          # Raw odds files
|   `-- normalized/   # Consolidated: odds_consolidated_canonical.csv
|-- ratings/
|   `-- barttorvik/   # barttorvik_YYYY.json
|-- backtest_datasets/  # Pre-built training data
|-- schemas/          # Field definitions
`-- ncaahoopR_data-master/  # Play-by-play (~7GB, not in git)
```

All scripts read/write directly to Azure Blob Storage. No local cache is used.

## Season Definitions (canonicalized)
- ESPN game dates: season = `year` if `month >= 11` else `year + 1` (Nov-Apr window).
- Odds API (`commence_time` UTC): apply the same rule after converting to date; beware late-night UTC rolling to next day.
- Barttorvik: season key equals championship year (e.g., 2024 file = 2023-24 season).
- Use this rule everywhere to align joins: **season = date.year if month >= 11 else date.year + 1**.

## Current Azure Coverage (canonical window)
- Full-game scores: seasons 2024+ (see `backtest_datasets/backtest_master.csv` metadata for counts).
- 1H scores: partial coverage in the canonical window; verify `scores/h1/h1_games_all.csv` before use.
- FG odds: consolidated in `odds/normalized/odds_consolidated_canonical.csv` (check metadata for opener completeness).
- 1H odds: limited coverage; validate market availability per season.
- Barttorvik ratings: seasons 2024+.

## Gaps to Fill
- **1H scores:** Coverage is incomplete within the canonical window.
- **Odds:** Ensure spreads/totals are complete for 2024+ and document any market gaps.
- **Ratings:** Ensure Barttorvik ratings exist for each canonical season.
- **Aliases:** Normalize new source spellings against `backtest_datasets/team_aliases_db.json` in Azure.

## Ingestion Steps (Azure-only scripts)
1) **Full-game scores + Barttorvik ratings (ESPN + Barttorvik)**
   - `python testing/scripts/fetch_historical_data.py --seasons 2024-2026 --format both`
   - Writes to Azure Blob `scores/fg/` and `ratings/barttorvik/`.

2) **1H scores (ESPN boxscores)**
   - After FG fetch, run `python testing/scripts/fetch_h1_data.py`
   - Uses `scores/fg/games_all.csv` -> outputs under `scores/h1/`.

3) **Odds (The Odds API)**
   - Requires `ODDS_API_KEY`. Fetch in chunks to respect quota/rate limits, e.g.:
     - `python testing/scripts/fetch_historical_odds.py --start 2023-11-01 --end 2024-04-15`
       - Repeat per season within the canonical window; outputs under `odds/raw/`.
   - Note: API may not expose 1H markets historically; document any missing markets after fetch.

4) **Aliases & Standardization**
   - Reconcile new team spellings against `backtest_datasets/team_aliases_db.json`; add entries as needed.
   - Keep metric names explicit (e.g., `tempo`, `adj_o`, `adj_d`, `barthag`) to avoid ambiguity.

5) **Validation Checklist**
   - Per-season row counts for FG, 1H, odds after fetch; confirm season key rule applied.
   - Spot-check late-night games (UTC rollover) to ensure correct season assignment.
   - Document any missing odds markets or seasons not provided by the source.

## Quick Commands Summary
- FG scores: `python testing/scripts/fetch_historical_data.py --seasons 2024-2026 --format both`
- 1H scores: `python testing/scripts/fetch_h1_data.py`
- Odds: `python testing/scripts/fetch_historical_odds.py --start <YYYY-MM-DD> --end <YYYY-MM-DD>`
