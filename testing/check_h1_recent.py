"""Check H1 data for 2024+."""
import csv

with open('data/h1_historical/h1_games_all.csv', 'r') as f:
    h1 = list(csv.DictReader(f))

# Get 2024-2025 games
recent = [r for r in h1 if r['date'] >= '2024-01-01']
print(f'H1 games from 2024+: {len(recent)}')
print()
print('Sample H1 games from 2024+:')
for g in recent[:10]:
    print(f"  {g['date']}: {g['away_team']} @ {g['home_team']} (H1: {g['away_h1']}-{g['home_h1']})")

# Check team name format
print()
print("H1 team names in 2024+:")
seen = set()
for g in recent:
    if g['home_team'] not in seen:
        print(f"  '{g['home_team']}'")
        seen.add(g['home_team'])
        if len(seen) >= 10:
            break
