Historical Odds Data
====================

- This folder is ignored by default; only curated, normalized artifacts are tracked in git.
- Tracked file: `odds_all_normalized_20201125_20260107.csv` (full-game + 1H pregame lines, `is_march_madness` flag, earliest timestamp per bookmaker, preferred bookmaker order: pinnacle > draftkings > fanduel > betmgm).
- Raw pulls, partial checkpoints, and other generated CSVs remain untracked; keep them here locally or in external storage.

Refresh workflow
1) Fetch missing ranges with `python testing/scripts/fetch_historical_odds.py --start YYYY-MM-DD --end YYYY-MM-DD` (or `--season 2025`) to `testing/data/historical_odds/`.
2) Merge/normalize into a new `odds_all_normalized_*.csv` (include h1 + full-game, add `is_march_madness`, dedupe keeping earliest snapshots and best bookmaker), then replace the tracked file.
3) Commit the updated normalized CSV and this README; leave other generated files untracked.
