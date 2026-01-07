"""Find remaining gaps between current match and ceiling."""
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
all_training_games = {}
for _, row in training.iterrows():
    date = row['game_date'][:10]
    home = norm(row['home_team'])
    away = norm(row['away_team'])
    all_training_games[(date, home, away)] = (row['home_team'], row['away_team'])

for _, row in games_all.iterrows():
    date = str(row['date'])[:10]
    home = norm(row['home_team'])
    away = norm(row['away_team'])
    if (date, home, away) not in all_training_games:
        all_training_games[(date, home, away)] = (row['home_team'], row['away_team'])

# Find odds games where training exists on same date but matchup doesn't match
unmatched_but_training_exists = []
unmatched_teams = Counter()

for _, row in odds.iterrows():
    date = row['game_date'][:10]
    home_raw = row['home_team']
    away_raw = row['away_team']
    home = norm(home_raw)
    away = norm(away_raw)
    
    # Check if this game exists in training
    if (date, home, away) not in all_training_games:
        # Check if there's ANY training game on this date
        training_on_date = [k for k in all_training_games.keys() if k[0] == date]
        if training_on_date:
            # There's training data for this date but not this game
            unmatched_teams[home] += 1
            unmatched_teams[away] += 1
            if len(unmatched_but_training_exists) < 30:
                unmatched_but_training_exists.append({
                    'date': date,
                    'odds_home': home_raw,
                    'odds_away': away_raw,
                    'norm_home': home,
                    'norm_away': away,
                })

print(f"Games where training exists for date but matchup doesn't match: {len(unmatched_but_training_exists)}")
print("\nTop 30 teams in these unmatched games:")
for team, cnt in unmatched_teams.most_common(30):
    print(f"  {team}: {cnt}")

print("\nSample unmatched (training exists for date):")
for g in unmatched_but_training_exists[:15]:
    print(f"  {g['date']}: {g['odds_home']} ({g['norm_home']}) vs {g['odds_away']} ({g['norm_away']})")
