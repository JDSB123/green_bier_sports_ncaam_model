"""Compare game counts on same date."""
import csv

test_date = '2024-01-06'  # A typical January Saturday

# Check odds
with open('data/historical_odds/odds_consolidated_canonical.csv', 'r') as f:
    odds = [r for r in csv.DictReader(f) if r['game_date'] == test_date]
print(f"Odds games on {test_date}: {len(odds)}")
for r in odds[:8]:
    print(f"  {r['away_team_canonical']} @ {r['home_team_canonical']}")

print()

# Check scores
with open('data/historical/games_2024.csv', 'r') as f:
    scores = [r for r in csv.DictReader(f) if r['date'] == test_date]
print(f"Score games on {test_date}: {len(scores)}")
for r in scores[:8]:
    print(f"  {r['away_team']} @ {r['home_team']}")
