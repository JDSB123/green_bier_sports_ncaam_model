"""Find the actual remaining team name issues vs data gaps."""
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

# Build normalized score lookup
score_keys = {}
for _, row in training.iterrows():
    date = str(row['game_date'])[:10]
    home = norm(row['home_team'])
    away = norm(row['away_team'])
    if home and away:
        score_keys[(date, home, away)] = 'training'

for _, row in games_all.iterrows():
    date = str(row['date'])[:10]
    home = norm(row['home_team'])
    away = norm(row['away_team'])
    if home and away and (date, home, away) not in score_keys:
        score_keys[(date, home, away)] = 'games_all'

# Check 2023-24 unmatched odds games
unmatched_2023 = []
matched_2023 = 0
for _, row in odds.iterrows():
    date = str(row['game_date'])[:10]
    if not date.startswith('2023-1') and not date.startswith('2024-0'):
        continue  # Only 2023-24 season
    
    home = norm(row['home_team'])
    away = norm(row['away_team'])
    key = (date, home, away)
    
    if key in score_keys:
        matched_2023 += 1
    else:
        # Check if this game exists with different team order (home/away swapped)
        swapped_key = (date, away, home)
        if swapped_key in score_keys:
            unmatched_2023.append((date, home, away, 'SWAPPED'))
        else:
            # Check if game exists on same date at all
            date_games = [k for k in score_keys.keys() if k[0] == date]
            found_similar = None
            for dg in date_games:
                if home[:5].lower() in dg[1].lower() or away[:5].lower() in dg[2].lower():
                    found_similar = dg
                    break
            if found_similar:
                unmatched_2023.append((date, home, away, f'SIMILAR: {found_similar[1]} vs {found_similar[2]}'))
            else:
                unmatched_2023.append((date, home, away, 'NO_DATA'))

print(f"2023-24 Season:")
print(f"  Matched: {matched_2023}")
print(f"  Unmatched: {len(unmatched_2023)}")
print()

# Categorize unmatched
by_reason = defaultdict(list)
for item in unmatched_2023:
    reason = item[3]
    if reason.startswith('SIMILAR'):
        by_reason['Team name issue'].append(item)
    elif reason == 'SWAPPED':
        by_reason['Home/away swapped'].append(item)
    else:
        by_reason['No score data'].append(item)

print("Breakdown:")
for reason, games in by_reason.items():
    print(f"  {reason}: {len(games)}")
    if reason == 'Team name issue' and games:
        print("    Examples:")
        for g in games[:10]:
            print(f"      {g[0]}: {g[1]} vs {g[2]} -> {g[3]}")
