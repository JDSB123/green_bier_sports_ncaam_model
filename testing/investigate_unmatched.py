"""Investigate remaining unmatched games."""
import pandas as pd
import json
from collections import Counter

# Load resolver
with open('../services/prediction-service-python/training_data/team_aliases_db.json', 'r') as f:
    resolver = json.load(f)

def normalize(name):
    """Normalize team name using resolver."""
    if not name:
        return None
    key = name.lower().strip()
    return resolver.get(key, name)

# Load data
odds = pd.read_csv('data/historical_odds/odds_consolidated_canonical.csv')
training = pd.read_csv('../services/prediction-service-python/training_data/training_data_with_odds.csv')

print(f"Odds: {len(odds)} games")
print(f"Training: {len(training)} games")

# Build training lookup by normalized names
training_keys = set()
for _, row in training.iterrows():
    home = normalize(row.get('home_team', row.get('team_home', '')))
    away = normalize(row.get('away_team', row.get('team_away', '')))
    date = str(row.get('date', row.get('game_date', '')))[:10]
    if home and away:
        training_keys.add((date, home, away))

print(f"Training keys: {len(training_keys)}")

# Find unmatched odds games
unmatched_teams = Counter()
unmatched_pairs = []
for _, row in odds.iterrows():
    home_raw = row.get('home_team', row.get('team_home', ''))
    away_raw = row.get('away_team', row.get('team_away', ''))
    home = normalize(home_raw)
    away = normalize(away_raw)
    date = str(row.get('game_date', row.get('date', '')))[:10]
    
    key = (date, home, away)
    if key not in training_keys:
        unmatched_teams[home] += 1
        unmatched_teams[away] += 1
        if len(unmatched_pairs) < 30:
            unmatched_pairs.append((date, home_raw, away_raw, home, away))

print(f"\nUnmatched: {len([k for k in odds.iterrows() if 1])} checking...")
print(f"\nTop 30 unmatched teams:")
for team, count in unmatched_teams.most_common(30):
    print(f"  {team}: {count} games")

print(f"\nSample unmatched games (raw -> normalized):")
for date, h_raw, a_raw, h_norm, a_norm in unmatched_pairs[:20]:
    print(f"  {date}: {h_raw} ({h_norm}) vs {a_raw} ({a_norm})")

# Also check what dates are in odds but not training
odds_dates = set(str(row.get('game_date', row.get('date', '')))[:10] for _, row in odds.iterrows())
training_dates = set(str(row.get('date', row.get('game_date', '')))[:10] for _, row in training.iterrows())
only_odds_dates = odds_dates - training_dates
print(f"\n\nDates in odds but NOT in training: {len(only_odds_dates)}")
print(f"  Sample: {sorted(list(only_odds_dates))[:20]}")
