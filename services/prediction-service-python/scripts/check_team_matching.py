#!/usr/bin/env python3
"""Check team name matching between Basketball API and Barttorvik."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT_DIR))

from testing.azure_io import read_csv, blob_exists
from testing.data_paths import DATA_PATHS
from testing.data_window import CANONICAL_START_SEASON

# Azure-only sources (single source of truth)
GAMES_BLOB = str(DATA_PATHS.backtest_datasets / "backtest_master.csv")
RATINGS_BLOB = str(DATA_PATHS.backtest_datasets / "barttorvik_ratings.csv")
H1_BLOB = str(DATA_PATHS.scores_h1 / "h1_games_all.csv")

def normalize(name):
    if not name:
        return ''
    name = str(name).lower().strip()
    name = name.replace('state', 'st')
    name = name.replace('university', '')
    name = name.replace('college', '')
    name = name.replace("'", '')
    name = name.replace('.', '')
    name = name.replace('-', ' ')
    return ' '.join(name.split())

df = read_csv(GAMES_BLOB)
ratings_df = read_csv(RATINGS_BLOB)

team_col = "team"
if team_col not in ratings_df.columns:
    if "team_name" in ratings_df.columns:
        team_col = "team_name"
    else:
        raise ValueError("Barttorvik ratings missing team column")

ratings = {str(name) for name in ratings_df[team_col].dropna().astype(str)}
ratings_normalized = {normalize(name) for name in ratings}

def is_d1(team):
    norm = normalize(team)
    if norm in ratings_normalized:
        return True
    for key in ratings:
        key_norm = normalize(key)
        if norm in key_norm or key_norm in norm:
            return True
    return False

# Check games
df['home_d1'] = df['home_team'].apply(is_d1)
df['away_d1'] = df['away_team'].apply(is_d1)
df['both_d1'] = df['home_d1'] & df['away_d1']

print("=" * 60)
print("TEAM MATCHING ANALYSIS")
print("=" * 60)

print("\nGame breakdown:")
print(f"  Total games: {len(df)}")
print(f"  Both D1: {df['both_d1'].sum()} ({100*df['both_d1'].mean():.1f}%)")
print(f"  At least one D1: {(df['home_d1'] | df['away_d1']).sum()}")
print(f"  Neither D1: {(~df['home_d1'] & ~df['away_d1']).sum()}")

# D1 vs D1 breakdown by season
if 'game_date' not in df.columns and 'date' in df.columns:
    df['game_date'] = df['date']
df['game_date'] = pd.to_datetime(df['game_date'])
df['season'] = df['game_date'].apply(lambda d: d.year + 1 if d.month >= 11 else d.year)
df = df[df['season'] >= CANONICAL_START_SEASON]

print("\nD1 vs D1 games by season:")
for season in sorted(df['season'].unique()):
    season_df = df[(df['season'] == season) & df['both_d1']]
    print(f"  {season-1}-{season}: {len(season_df)} games")

# Unique teams
all_teams = set(df['home_team']) | set(df['away_team'])
d1_teams = set(df[df['home_d1']]['home_team']) | set(df[df['away_d1']]['away_team'])
non_d1_teams = all_teams - d1_teams

print(f"\nUnique teams: {len(all_teams)}")
print(f"  D1 teams: {len(d1_teams)}")
print(f"  Non-D1 teams: {len(non_d1_teams)}")

# Sample D1 team matches
print("\nSample D1 teams (matched):")
sample_d1 = sorted(d1_teams)[:10]
for team in sample_d1:
    norm = normalize(team)
    match_key = norm if norm in ratings else "partial"
    print(f"  {team} -> {match_key}")

# Sample unmatched high-frequency teams
team_counts = df['home_team'].value_counts().add(df['away_team'].value_counts(), fill_value=0)
unmatched_counts = team_counts[team_counts.index.isin(non_d1_teams)].sort_values(ascending=False)

print("\nTop unmatched teams by game count:")
for team, count in unmatched_counts.head(15).items():
    print(f"  {team}: {int(count)} games")

# Check 1H data availability
print("\n" + "=" * 60)
print("1ST HALF DATA")
print("=" * 60)

if 'home_h1_score' in df.columns:
    has_h1 = df['home_h1_score'].notna().sum()
    print(f"Games with 1H scores: {has_h1}")
else:
    print("No 1H score columns in Basketball API data")

# Check the H1 historical file
if blob_exists(H1_BLOB):
    h1_df = read_csv(H1_BLOB)
    print(f"\nH1 Historical CSV found: {len(h1_df)} games")
    print(f"Columns: {list(h1_df.columns)}")
    if len(h1_df) > 0:
        print(f"Sample: {h1_df.iloc[0].to_dict()}")
else:
    print(f"\nH1 Historical CSV not found at {H1_BLOB}")
