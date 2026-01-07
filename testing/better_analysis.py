"""Better analysis of remaining unmatched games."""
import pandas as pd
import json
from collections import defaultdict

with open('../services/prediction-service-python/training_data/team_aliases_db.json', 'r') as f:
    resolver = json.load(f)

def norm(name):
    if not name or pd.isna(name): return ''
    return resolver.get(str(name).lower().strip(), name)

# Load all data
training = pd.read_csv('../services/prediction-service-python/training_data/training_data_with_odds.csv')
games_all = pd.read_csv('data/historical/games_all.csv')
odds = pd.read_csv('data/historical_odds/odds_consolidated_canonical.csv')

# Build score keys (try both orders)
score_keys = set()
for _, row in training.iterrows():
    date = str(row['game_date'])[:10]
    home = norm(row['home_team'])
    away = norm(row['away_team'])
    if home and away:
        score_keys.add((date, home, away))
        score_keys.add((date, away, home))  # Add swapped too

for _, row in games_all.iterrows():
    date = str(row['date'])[:10]
    home = norm(row['home_team'])
    away = norm(row['away_team'])
    if home and away:
        score_keys.add((date, home, away))
        score_keys.add((date, away, home))

print(f"Total score keys (with swaps): {len(score_keys)}")

# Check matching
matched = 0
unmatched_by_season = defaultdict(list)

for _, row in odds.iterrows():
    date = str(row['game_date'])[:10]
    home = norm(row['home_team'])
    away = norm(row['away_team'])
    
    yr = int(date[:4])
    mo = int(date[5:7])
    season = f"{yr}-{yr+1}" if mo >= 8 else f"{yr-1}-{yr}"
    
    if (date, home, away) in score_keys:
        matched += 1
    else:
        unmatched_by_season[season].append((date, home, away, row['home_team'], row['away_team']))

print(f"\nTotal matched: {matched}/{len(odds)} ({matched*100//len(odds)}%)")
print(f"\nUnmatched by season:")
for season in sorted(unmatched_by_season.keys()):
    print(f"  {season}: {len(unmatched_by_season[season])}")

# Deep dive on 2023-24 unmatched
print(f"\n=== 2023-24 UNMATCHED (showing RAW names) ===")
for item in unmatched_by_season['2023-2024'][:30]:
    date, norm_home, norm_away, raw_home, raw_away = item
    print(f"  {date}: {norm_home} vs {norm_away}")
    print(f"           RAW: {raw_home} vs {raw_away}")
