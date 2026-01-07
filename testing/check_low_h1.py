"""Check low H1 scoring games."""
import csv

with open('data/backtest_ready.csv', 'r') as f:
    rows = list(csv.DictReader(f))

# Find the low H1 scoring games
low_h1 = []
for r in rows:
    if r.get('h1_home_score') and r.get('h1_away_score'):
        try:
            h1_home = float(r['h1_home_score'])
            h1_away = float(r['h1_away_score'])
            if h1_home < 15 or h1_away < 15:
                low_h1.append(r)
        except:
            pass

print(f"Games with H1 score < 15: {len(low_h1)}")
print()
for g in low_h1:
    print(f"{g['game_date']}: {g['away_team']} @ {g['home_team']}")
    print(f"  H1: {g['h1_away_score']}-{g['h1_home_score']}")
    print(f"  Final: {g['away_score']}-{g['home_score']}")
    print()
