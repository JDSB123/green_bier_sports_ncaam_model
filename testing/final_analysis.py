"""Final analysis of match rate ceiling."""
import pandas as pd
import json
from collections import defaultdict

with open('../services/prediction-service-python/training_data/team_aliases_db.json', 'r') as f:
    resolver = json.load(f)

def norm(name):
    if not name: return name
    return resolver.get(name.lower().strip(), name)

odds = pd.read_csv('data/historical_odds/odds_consolidated_canonical.csv')
training = pd.read_csv('../services/prediction-service-python/training_data/training_data_with_odds.csv')
games_all = pd.read_csv('data/historical/games_all.csv')

# Build training lookup with ALL games
all_training_games = set()
for _, row in training.iterrows():
    date = row['game_date'][:10]
    home = norm(row['home_team'])
    away = norm(row['away_team'])
    all_training_games.add((date, home, away))

for _, row in games_all.iterrows():
    date = str(row['date'])[:10]
    home = norm(row['home_team'])
    away = norm(row['away_team'])
    all_training_games.add((date, home, away))

print(f"Total training games (normalized): {len(all_training_games)}")
print(f"Total odds games: {len(odds)}")

# For each odds game, check if there's a training game on same date
by_date_status = defaultdict(lambda: {'has_training': 0, 'no_training': 0})

for _, row in odds.iterrows():
    date = row['game_date'][:10]
    home = norm(row['home_team'])
    away = norm(row['away_team'])
    
    if (date, home, away) in all_training_games:
        by_date_status[date]['has_training'] += 1
    else:
        by_date_status[date]['no_training'] += 1

# Count days where NO training exists
days_no_training = [d for d, v in by_date_status.items() if v['has_training'] == 0]
days_partial = [d for d, v in by_date_status.items() if v['has_training'] > 0 and v['no_training'] > 0]
days_full = [d for d, v in by_date_status.items() if v['no_training'] == 0]

print(f"\nDays analysis:")
print(f"  Days with NO training data: {len(days_no_training)}")
print(f"  Days with PARTIAL training data: {len(days_partial)}")
print(f"  Days with FULL training coverage: {len(days_full)}")

# Calculate expected match rate ceiling
total_matchable = sum(v['has_training'] for v in by_date_status.values())
print(f"\nTheoretical ceiling:")
print(f"  Matchable games: {total_matchable}")
print(f"  Ceiling match rate: {total_matchable/len(odds)*100:.1f}%")

# For 2023-2024 specifically
odds_2324 = odds[(odds['game_date'] >= '2023-11-01') & (odds['game_date'] < '2024-05-01')]
matched_2324 = 0
for _, row in odds_2324.iterrows():
    date = row['game_date'][:10]
    home = norm(row['home_team'])
    away = norm(row['away_team'])
    if (date, home, away) in all_training_games:
        matched_2324 += 1

print(f"\n2023-24 season:")
print(f"  Odds games: {len(odds_2324)}")
print(f"  Matched: {matched_2324} ({matched_2324/len(odds_2324)*100:.1f}%)")
