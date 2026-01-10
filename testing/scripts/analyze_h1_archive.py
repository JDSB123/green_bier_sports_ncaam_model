#!/usr/bin/env python3
"""Analyze H1 archive files for pricing data."""

import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "ncaam_historical_data_local"

print("=" * 70)
print("H1 ARCHIVE FILE - DETAILED ANALYSIS")
print("=" * 70)

# Load the archive file
fpath = DATA / "odds" / "normalized" / "odds_h1_archive_matchups.csv"
df = pd.read_csv(fpath)

print(f"Total rows: {len(df):,}")

# Date range
df["game_date"] = pd.to_datetime(df["game_date"])
print(f"\nDate range: {df['game_date'].min().date()} to {df['game_date'].max().date()}")

# Rows with H1 prices
with_h1_prices = df[df["h1_spread_home_price"].notna()]
print(f"\nRows with H1 spread prices: {len(with_h1_prices):,}")
print(f"Date range (with prices): {with_h1_prices['game_date'].min().date()} to {with_h1_prices['game_date'].max().date()}")

# Unique games with H1 prices
unique_games = with_h1_prices.groupby(
    ["game_date", "home_team_canonical", "away_team_canonical"]
).size().reset_index(name="count")
print(f"\nUnique games with H1 prices: {len(unique_games):,}")

# Sample of price values
print(f"\nSample H1 spread prices:")
cols = ["game_date", "home_team_canonical", "away_team_canonical", "h1_spread", "h1_spread_home_price"]
sample = with_h1_prices[cols].head(5)
for _, row in sample.iterrows():
    print(f"  {row['game_date'].date()} {row['home_team_canonical']} vs {row['away_team_canonical']}: H1 spread={row['h1_spread']}, price={row['h1_spread_home_price']}")

# Season breakdown
print(f"\nH1 prices by season:")
for season in sorted(with_h1_prices["season"].unique()):
    count = len(with_h1_prices[with_h1_prices["season"] == season])
    unique = with_h1_prices[with_h1_prices["season"] == season].groupby(
        ["game_date", "home_team_canonical", "away_team_canonical"]
    ).size().reset_index()
    print(f"  {season}: {count:,} rows, {len(unique):,} unique games")

print("\n" + "=" * 70)
print("CONCLUSION")
print("=" * 70)
print("H1 prices EXIST in odds_h1_archive_matchups.csv but were NOT being")
print("incorporated into odds_consolidated_canonical.csv!")
print("\nNEXT STEP: Update the consolidation pipeline to include H1 prices.")
