"""Debug why 2020-11-25 games don't match."""
import pandas as pd
import json

with open('../services/prediction-service-python/training_data/team_aliases_db.json', 'r') as f:
    resolver = json.load(f)

def norm(name):
    if not name: return name
    return resolver.get(name.lower().strip(), name)

training = pd.read_csv('../services/prediction-service-python/training_data/training_data_with_odds.csv')
games_all = pd.read_csv('data/historical/games_all.csv')
odds = pd.read_csv('data/historical_odds/odds_consolidated_canonical.csv')

# Check 2020-11-25 games
date = '2020-11-25'

print(f"=== {date} ===")
print(f"\nODDS games on this date:")
odds_date = odds[odds['game_date'] == date]
for _, row in odds_date.head(10).iterrows():
    h, a = norm(row['home_team']), norm(row['away_team'])
    print(f"  {row['home_team']} ({h}) vs {row['away_team']} ({a})")

print(f"\nGAMES_ALL games on this date:")
games_date = games_all[games_all['date'] == date]
for _, row in games_date.head(10).iterrows():
    h, a = norm(row['home_team']), norm(row['away_team'])
    print(f"  {row['home_team']} ({h}) vs {row['away_team']} ({a})")

# Check if specific game matches
# Odds: Michigan State Spartans vs Eastern Michigan Eagles
# games_all: ?
print(f"\nLooking for Michigan State game:")
for _, row in odds_date.iterrows():
    if 'Michigan' in row['home_team']:
        odds_h = norm(row['home_team'])
        odds_a = norm(row['away_team'])
        print(f"  Odds: {row['home_team']} ({odds_h}) vs {row['away_team']} ({odds_a})")
        
        # Find in games_all
        for _, g in games_date.iterrows():
            if 'Michigan' in g['home_team']:
                games_h = norm(g['home_team'])
                games_a = norm(g['away_team'])
                print(f"  games_all: {g['home_team']} ({games_h}) vs {g['away_team']} ({games_a})")
                print(f"  Match: {odds_h == games_h and odds_a == games_a}")
