"""Check odds file format for major programs."""
import csv

with open('data/historical_odds/odds_consolidated_canonical.csv', 'r') as f:
    odds = list(csv.DictReader(f))

# Find Michigan State games
msu = [r for r in odds if 'michigan' in r.get('home_team_canonical', '').lower() or 'michigan' in r.get('away_team_canonical', '').lower()][:5]
print('Michigan games in odds:')
for g in msu:
    print(f"  Home: '{g['home_team_canonical']}', Away: '{g['away_team_canonical']}'")

# Check date format
print()
print('Date format:')
print(f"  game_date: '{odds[1000].get('game_date', 'N/A')}'")
print(f"  commence_time: '{odds[1000].get('commence_time', 'N/A')}'")

# Count games by year-month
from collections import defaultdict
by_ym = defaultdict(int)
for r in odds:
    date = r.get('game_date', r.get('commence_time', ''))[:7]
    by_ym[date] += 1

print()
print('Games by year-month (first 10):')
for ym in sorted(by_ym.keys())[:10]:
    print(f"  {ym}: {by_ym[ym]}")
