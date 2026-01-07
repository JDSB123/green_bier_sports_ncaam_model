"""Find all mismatched team pairs and add missing mappings."""
import pandas as pd
import json
from collections import Counter

# Load resolver
resolver_path = '../services/prediction-service-python/training_data/team_aliases_db.json'
with open(resolver_path, 'r') as f:
    resolver = json.load(f)

def norm(name):
    if not name: return name
    return resolver.get(name.lower().strip(), name)

# Load data
odds = pd.read_csv('data/historical_odds/odds_consolidated_canonical.csv')
training = pd.read_csv('../services/prediction-service-python/training_data/training_data_with_odds.csv')
games_all = pd.read_csv('data/historical/games_all.csv')

# Build training lookup (normalized)
training_games = {}
for _, row in training.iterrows():
    date = row['game_date'][:10]
    home = norm(row['home_team'])
    away = norm(row['away_team'])
    key = (date, home, away)
    training_games[key] = (row['home_team'], row['away_team'])

# Also add from games_all
for _, row in games_all.iterrows():
    date = str(row['date'])[:10]
    home = norm(row['home_team'])
    away = norm(row['away_team'])
    key = (date, home, away)
    if key not in training_games:
        training_games[key] = (row['home_team'], row['away_team'])

print(f"Training games: {len(training_games)}")

# Find mismatches in 2023+ data
mismatched_home = Counter()
mismatched_away = Counter()
matched = 0
for _, row in odds[odds['game_date'] >= '2023-11-01'].iterrows():
    date = row['game_date'][:10]
    home_raw = row['home_team']
    away_raw = row['away_team']
    home = norm(home_raw)
    away = norm(away_raw)
    key = (date, home, away)
    
    if key in training_games:
        matched += 1
    else:
        # Check if there's a game on same date with similar teams
        found = False
        for tkey, (th, ta) in training_games.items():
            if tkey[0] == date:
                # Check if one team matches
                th_norm = norm(th)
                ta_norm = norm(ta)
                if home in [th_norm, ta_norm] or away in [th_norm, ta_norm]:
                    # Found partial match
                    if home != th_norm and home not in [ta_norm]:
                        mismatched_home[f"{home_raw} ({home}) vs {th}"] += 1
                    if away != ta_norm and away not in [th_norm]:
                        mismatched_away[f"{away_raw} ({away}) vs {ta}"] += 1
                    found = True
                    break

print(f"Matched: {matched}")
print(f"\nTop 30 home team mismatches:")
for pair, cnt in mismatched_home.most_common(30):
    print(f"  {pair}: {cnt}")

print(f"\nTop 30 away team mismatches:")
for pair, cnt in mismatched_away.most_common(30):
    print(f"  {pair}: {cnt}")

# Get all unique odds team names
all_odds_teams = set(odds['home_team'].unique()) | set(odds['away_team'].unique())
all_training_teams = set(training['home_team'].unique()) | set(training['away_team'].unique())
all_training_teams |= set(games_all['home_team'].unique()) | set(games_all['away_team'].unique())

# Find teams that appear in odds but not training after normalization
odds_normalized = {norm(t) for t in all_odds_teams}
training_normalized = {norm(t) for t in all_training_teams}
only_in_odds = odds_normalized - training_normalized

print(f"\nTeams in odds but not training (normalized): {len(only_in_odds)}")
for t in sorted(only_in_odds)[:50]:
    print(f"  {t}")
