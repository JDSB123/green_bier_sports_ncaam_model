<!-- Purpose: document current historical coverage, season rules, gaps, and how to fetch missing data. -->
# Historical Data Coverage, Season Rules, and Gaps

## Season Definitions (canonicalized)
- ESPN game dates: season = `year` if `month >= 11` else `year + 1` (Nov–Apr window).
- Odds API (`commence_time` UTC): apply the same rule after converting to date; beware late-night UTC rolling to next day.
- Barttorvik: season key equals championship year (e.g., 2024 file = 2023–24 season).
- Use this rule everywhere to align joins: **season = date.year if month >= 11 else date.year + 1**.

## Current On-Disk Coverage (as of Jan 2026 snapshot)
- Full-game scores (`services/prediction-service-python/training_data/games_2023_2025.csv`): seasons 2023–2026 counts = {2023: 2,518, 2024: 2,573, 2025: 3,329, 2026: 3,343}.
- 1H scores (`testing/data/h1_historical/h1_games_all.csv`): seasons 2019–2022 counts = {2019: 292, 2020: 175, 2021: 563, 2022: 16}. No 2023–2026 1H data present.
- FG odds sample (`training_data_with_odds.csv`): mirrors FG counts above but many rows have empty openers.
- 1H odds sample (`h1_historical_odds.csv`): only 194 rows in season 2025; no breadth or prior seasons.
- Barttorvik ratings (`training_data/barttorvik_ratings.csv`, `barttorvik_lookup.json`): only 2024–2025 seasons.

## Gaps to Fill
- **FG scores:** Missing seasons 2019–2022 (and any 2026 games beyond current snapshot).
- **1H scores:** Missing most of 2022 and all of 2023–2026.
- **Odds:** No historical spreads/totals for 2019–2024; no broad 1H odds history.
- **Ratings:** Missing Barttorvik 2019–2023 to match backtest window.
- **Aliases:** Need to normalize any new source spellings against `training_data/team_aliases_db.json`.

## Ingestion Steps (existing scripts)
1) **Full-game scores (ESPN)**
   - `python testing/scripts/fetch_historical_data.py --seasons 2019-2026 --format both --output-dir testing/data/historical`
   - Produces `games_YYYY.csv/json` and `barttorvik_YYYY.json`.

2) **1H scores (ESPN boxscores)**
   - After FG fetch, run `python testing/scripts/fetch_h1_data.py`
   - Uses `testing/data/historical/games_all.csv` → outputs `testing/data/h1_historical/h1_games_all.csv` and JSON.

3) **Odds (The Odds API)**
   - Requires `ODDS_API_KEY`. Fetch in chunks to respect quota/rate limits, e.g.:
     - `python testing/scripts/fetch_historical_odds.py --start 2019-11-01 --end 2020-04-15`
     - Repeat per season through 2025-04-15; outputs to `testing/data/historical_odds/odds_*.csv`.
   - Note: API may not expose 1H markets historically; document any missing markets after fetch.

4) **Barttorvik ratings (public JSON)**
   - For each season 2019–2023, download `https://barttorvik.com/{YEAR}_team_results.json` to `testing/data/historical/barttorvik_{YEAR}.json`.
   - Optionally convert/append to `services/prediction-service-python/training_data/barttorvik_ratings.csv` for model use.

5) **Aliases & Standardization**
   - Reconcile new team spellings against `training_data/team_aliases_db.json`; add entries as needed.
   - Keep metric names explicit (e.g., `tempo`, `adj_o`, `adj_d`, `barthag`) to avoid ambiguity (tempo vs efficiency).

6) **Validation Checklist**
   - Per-season row counts for FG, 1H, odds after fetch; confirm season key rule applied.
   - Spot-check late-night games (UTC rollover) to ensure correct season assignment.
   - Document any missing odds markets or seasons not provided by the source.

## Quick Commands Summary
- FG scores: `python testing/scripts/fetch_historical_data.py --seasons 2019-2026 --format both`
- 1H scores: `python testing/scripts/fetch_h1_data.py`
- Odds: `python testing/scripts/fetch_historical_odds.py --start <YYYY-MM-DD> --end <YYYY-MM-DD> --output testing/data/historical_odds/odds_<range>.csv`
- Barttorvik: download `{YEAR}_team_results.json` for 2019–2023
