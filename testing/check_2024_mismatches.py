"""Find remaining 2023-24 mismatches."""
import pandas as pd
import json
from collections import Counter

with open('../services/prediction-service-python/training_data/team_aliases_db.json', 'r') as f:
    resolver = json.load(f)

def norm(name):
    if not name: return name
    return resolver.get(name.lower().strip(), name)

odds = pd.read_csv('data/historical_odds/odds_consolidated_canonical.csv')
training = pd.read_csv('../services/prediction-service-python/training_data/training_data_with_odds.csv')
games_all = pd.read_csv('data/historical/games_all.csv')

# Build training lookup
training_keys = {}
for _, row in training.iterrows():
    date = row['game_date'][:10]
    home = norm(row['home_team'])
    away = norm(row['away_team'])
    training_keys[(date, home, away)] = (row['home_team'], row['away_team'])

for _, row in games_all.iterrows():
    date = str(row['date'])[:10]
    home = norm(row['home_team'])
    away = norm(row['away_team'])
    if (date, home, away) not in training_keys:
        training_keys[(date, home, away)] = (row['home_team'], row['away_team'])

# Check 2024 mismatches
odds_2024 = odds[(odds['game_date'] >= '2024-01-01') & (odds['game_date'] < '2024-05-01')]
print(f"Odds 2024: {len(odds_2024)} games")

unmatched_teams = Counter()
sample_mismatches = []
for _, row in odds_2024.iterrows():
    date = row['game_date'][:10]
    home_raw = row['home_team']
    away_raw = row['away_team']
    home = norm(home_raw)
    away = norm(away_raw)
    key = (date, home, away)
    
    if key not in training_keys:
        unmatched_teams[home] += 1
        unmatched_teams[away] += 1
        if len(sample_mismatches) < 20:
            sample_mismatches.append((date, home_raw, away_raw, home, away))

print(f"\nTop 30 unmatched teams in 2024:")
for team, cnt in unmatched_teams.most_common(30):
    print(f"  {team}: {cnt}")

print(f"\nSample mismatches:")
for date, hr, ar, h, a in sample_mismatches[:10]:
    print(f"  {date}: {hr} ({h}) vs {ar} ({a})")
