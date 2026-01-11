#!/usr/bin/env python3
"""Quick audit of available data sources for backtesting."""

import pandas as pd

from testing.azure_io import read_csv, list_files

print("=== DATA SOURCES AUDIT ===\n")

# 1. Games/Scores
games = read_csv("scores/fg/games_all.csv")
games["game_date"] = pd.to_datetime(games["game_date"])
print("1. GAMES (games_all.csv)")
print(f"   Rows: {len(games):,}")
print(f"   Date range: {games['game_date'].min().date()} to {games['game_date'].max().date()}")
print(f"   Columns: {list(games.columns)}")
print()

# 2. FG Spreads
fg_spreads = read_csv("odds/canonical/spreads/fg/spreads_fg_all.csv")
fg_spreads["game_date"] = pd.to_datetime(fg_spreads["game_date"])
print("2. FG SPREADS (spreads_fg_all.csv)")
print(f"   Rows: {len(fg_spreads):,}")
print(f"   Date range: {fg_spreads['game_date'].min().date()} to {fg_spreads['game_date'].max().date()}")
print(f"   Columns: {list(fg_spreads.columns)}")
print()

# 3. FG Totals
fg_totals = read_csv("odds/canonical/totals/fg/totals_fg_all.csv")
fg_totals["game_date"] = pd.to_datetime(fg_totals["game_date"])
print("3. FG TOTALS (totals_fg_all.csv)")
print(f"   Rows: {len(fg_totals):,}")
print(f"   Date range: {fg_totals['game_date'].min().date()} to {fg_totals['game_date'].max().date()}")
print(f"   Columns: {list(fg_totals.columns)}")
print()

# 4. H1 Spreads
h1_spreads = read_csv("odds/canonical/spreads/h1/spreads_h1_all.csv")
h1_spreads["game_date"] = pd.to_datetime(h1_spreads["game_date"])
print("4. H1 SPREADS (spreads_h1_all.csv)")
print(f"   Rows: {len(h1_spreads):,}")
print(f"   Date range: {h1_spreads['game_date'].min().date()} to {h1_spreads['game_date'].max().date()}")
print(f"   Columns: {list(h1_spreads.columns)}")
print()

# 5. H1 Totals
h1_totals = read_csv("odds/canonical/totals/h1/totals_h1_all.csv")
h1_totals["game_date"] = pd.to_datetime(h1_totals["game_date"])
print("5. H1 TOTALS (totals_h1_all.csv)")
print(f"   Rows: {len(h1_totals):,}")
print(f"   Date range: {h1_totals['game_date'].min().date()} to {h1_totals['game_date'].max().date()}")
print(f"   Columns: {list(h1_totals.columns)}")
print()

# 6. Barttorvik ratings
rating_files = list_files("ratings/", pattern="*.csv") + list_files("ratings/", pattern="*.json")
if rating_files:
    print("6. BARTTORVIK RATINGS (ratings/)")
    print(f"   Files: {[f.split('/')[-1] for f in rating_files]}")
else:
    print("6. BARTTORVIK RATINGS: NOT FOUND")
