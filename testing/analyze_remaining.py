"""Analyze what's still unmatched after fixes."""
import pandas as pd
import json
from collections import defaultdict

with open('../services/prediction-service-python/training_data/team_aliases_db.json', 'r') as f:
    resolver = json.load(f)

def norm(name):
    if not name or pd.isna(name): return ''
    return resolver.get(str(name).lower().strip(), name)

# Load data
training = pd.read_csv('../services/prediction-service-python/training_data/training_data_with_odds.csv')
games_all = pd.read_csv('data/historical/games_all.csv')
odds = pd.read_csv('data/historical_odds/odds_consolidated_canonical.csv')

# Build score keys
score_keys = set()
for _, row in training.iterrows():
    date = str(row['game_date'])[:10]
    home = norm(row['home_team'])
    away = norm(row['away_team'])
    if home and away:
        score_keys.add((date, home, away))

for _, row in games_all.iterrows():
    date = str(row['date'])[:10]
    home = norm(row['home_team'])
    away = norm(row['away_team'])
    if home and away:
        score_keys.add((date, home, away))

print(f"Total score keys: {len(score_keys)}")

# Build odds keys and track unmatched
unmatched_by_season = defaultdict(list)
matched = 0
for _, row in odds.iterrows():
    date = str(row['game_date'])[:10]
    home = norm(row['home_team'])
    away = norm(row['away_team'])
    key = (date, home, away)
    
    yr = int(date[:4])
    mo = int(date[5:7])
    season = f"{yr}-{yr+1}" if mo >= 8 else f"{yr-1}-{yr}"
    
    if key in score_keys:
        matched += 1
    else:
        unmatched_by_season[season].append(key)

print(f"Matched: {matched}/{len(odds)} ({matched*100//len(odds)}%)")
print()
print("Unmatched by season:")
for season in sorted(unmatched_by_season.keys()):
    games = unmatched_by_season[season]
    print(f"  {season}: {len(games)} unmatched")
    if len(games) <= 10:
        for g in games[:5]:
            print(f"    {g}")

# Show sample from 2023-24
print("\n\nSample unmatched from 2023-24:")
for g in unmatched_by_season['2023-2024'][:20]:
    print(f"  {g[0]}: {g[1]} vs {g[2]}")
    # Check if this game exists anywhere in score data with ANY team names
    date_games = [sk for sk in score_keys if sk[0] == g[0]]
    for sg in date_games:
        if g[1][:4].lower() in sg[1].lower() or g[2][:4].lower() in sg[2].lower():
            print(f"    Similar in scores: {sg[1]} vs {sg[2]}")
