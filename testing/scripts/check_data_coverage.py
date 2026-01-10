#!/usr/bin/env python3
"""Check data coverage for games and prices."""

import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "ncaam_historical_data_local"

print("=" * 60)
print("DATA COVERAGE ANALYSIS")
print("=" * 60)

# Check games_all.csv
print("\n1. Games Coverage (scores)")
print("-" * 40)

all_games_file = DATA / "scores" / "fg" / "games_all.csv"
all_games = pd.read_csv(all_games_file)
if "date" in all_games.columns:
    all_games["game_date"] = pd.to_datetime(all_games["date"])
else:
    all_games["game_date"] = pd.to_datetime(all_games["game_date"])

print(f"games_all.csv: {len(all_games):,} games")
print(f"Date range: {all_games['game_date'].min().date()} to {all_games['game_date'].max().date()}")

# Check individual year files
print("\nIndividual year files:")
total_from_years = 0
for year in range(2019, 2027):
    year_file = DATA / "scores" / "fg" / f"games_{year}.csv"
    if year_file.exists():
        df = pd.read_csv(year_file)
        if "date" in df.columns:
            df["game_date"] = pd.to_datetime(df["date"])
        else:
            df["game_date"] = pd.to_datetime(df["game_date"])
        print(f"  {year}: {len(df):,} games ({df['game_date'].min().date()} to {df['game_date'].max().date()})")
        total_from_years += len(df)
print(f"Total from year files: {total_from_years:,}")

# Check prices
print("\n2. Prices Coverage (odds)")
print("-" * 40)

odds = pd.read_csv(DATA / "odds" / "normalized" / "odds_consolidated_canonical.csv")
odds["game_date"] = pd.to_datetime(odds["game_date"])

print(f"Total odds rows: {len(odds):,}")
print(f"Date range: {odds['game_date'].min().date()} to {odds['game_date'].max().date()}")

# Unique games
unique_games = odds.groupby(["game_date", "home_team", "away_team"]).size().reset_index()
print(f"Unique games with odds: {len(unique_games):,}")

# With prices
with_prices = odds[odds["spread_home_price"].notna()]
print(f"\nRows with spread_home_price: {len(with_prices):,}")
print(f"Date range with prices: {with_prices['game_date'].min().date()} to {with_prices['game_date'].max().date()}")

unique_with_prices = with_prices.groupby(["game_date", "home_team", "away_team"]).size().reset_index()
print(f"Unique games with prices: {len(unique_with_prices):,}")

# Summary
print("\n3. OVERLAP ANALYSIS")
print("-" * 40)

# Check if year files have games in price range
for year in [2020, 2021, 2022, 2023]:
    year_file = DATA / "scores" / "fg" / f"games_{year}.csv"
    if year_file.exists():
        df = pd.read_csv(year_file)
        if "date" in df.columns:
            df["game_date"] = pd.to_datetime(df["date"])
        else:
            df["game_date"] = pd.to_datetime(df["game_date"])
        
        # Games before April 2023 (have prices)
        before_april = df[df["game_date"] < "2023-04-05"]
        print(f"  {year}: {len(before_april):,} games before April 2023 (could have prices)")

print("\n4. RECOMMENDATION")
print("-" * 40)
print("The build script only uses games_all.csv which starts from 2023-11-06.")
print("But individual year files have games from 2019-2023 that overlap with prices.")
print("\nTO FIX: Modify build_backtest_dataset.py to include ALL historical games")
print("from individual year files (2020-2023) that have matching price data.")
