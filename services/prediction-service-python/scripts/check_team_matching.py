#!/usr/bin/env python3
"""Check team name matching between Basketball API and Barttorvik."""
import pandas as pd
import json
from pathlib import Path

# Load data
games_path = Path(__file__).parent.parent / "training_data" / "games_2023_2025.csv"
ratings_path = Path(__file__).parent.parent / "training_data" / "barttorvik_lookup.json"

df = pd.read_csv(games_path)
with open(ratings_path) as f:
    ratings = json.load(f)

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

def is_d1(team):
    norm = normalize(team)
    if norm in ratings:
        return True
    for key in ratings:
        if norm in key or key in norm:
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
df['game_date'] = pd.to_datetime(df['game_date'])
df['season'] = df['game_date'].apply(lambda d: d.year + 1 if d.month >= 11 else d.year)

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
h1_path = Path(__file__).parent.parent.parent.parent / "testing" / "data" / "h1_historical" / "h1_games_all.csv"
if h1_path.exists():
    h1_df = pd.read_csv(h1_path)
    print(f"\nH1 Historical CSV found: {len(h1_df)} games")
    print(f"Columns: {list(h1_df.columns)}")
    if len(h1_df) > 0:
        print(f"Sample: {h1_df.iloc[0].to_dict()}")
else:
    print(f"\nH1 Historical CSV not found at {h1_path}")
