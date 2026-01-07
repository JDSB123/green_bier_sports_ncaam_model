"""Examine score data closely."""
import csv
from pathlib import Path

# Check the games_2024.csv more closely
with open('data/historical/games_2024.csv', 'r') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print(f"Total games in 2024: {len(rows)}")

# Check date range
dates = sorted(set(r['date'] for r in rows))
print(f"Date range: {dates[0]} to {dates[-1]}")

# Check for specific teams we know should match
duke_games = [r for r in rows if 'Duke' in r['home_team'] or 'Duke' in r['away_team']]
print(f"\nDuke games: {len(duke_games)}")
for g in duke_games[:5]:
    print(f"  {g['date']}: {g['away_team']} @ {g['home_team']} ({g['away_score']}-{g['home_score']})")

# Now compare to odds
with open('data/historical_odds/odds_consolidated_canonical.csv', 'r') as f:
    odds = list(csv.DictReader(f))

duke_odds = [r for r in odds if r['home_team_canonical'] == 'Duke' or r['away_team_canonical'] == 'Duke']
print(f"\nDuke odds games: {len(duke_odds)}")
for g in duke_odds[:5]:
    print(f"  {g['game_date']}: {g['away_team_canonical']} @ {g['home_team_canonical']} (spread {g['spread']})")
