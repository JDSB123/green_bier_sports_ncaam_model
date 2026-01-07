"""Debug team name mismatches between sources."""
import csv

# Sample from training data
with open('../services/prediction-service-python/training_data/training_data_with_odds.csv', 'r') as f:
    training = list(csv.DictReader(f))

# Sample from odds
with open('data/historical_odds/odds_consolidated_canonical.csv', 'r') as f:
    odds = list(csv.DictReader(f))

# Sample from H1
with open('data/h1_historical/h1_games_all.csv', 'r') as f:
    h1 = list(csv.DictReader(f))

print("TRAINING DATA team names (first 15):")
seen = set()
for r in training[:200]:
    if r['home_team'] not in seen:
        print(f"  '{r['home_team']}'")
        seen.add(r['home_team'])
        if len(seen) >= 15:
            break

print()
print("ODDS DATA team names (first 15):")
seen = set()
for r in odds[:200]:
    name = r.get('home_team_canonical', r.get('home_team', ''))
    if name not in seen:
        print(f"  '{name}'")
        seen.add(name)
        if len(seen) >= 15:
            break

print()
print("H1 DATA team names (first 15):")
seen = set()
for r in h1[:200]:
    if r['home_team'] not in seen:
        print(f"  '{r['home_team']}'")
        seen.add(r['home_team'])
        if len(seen) >= 15:
            break

# Now check a specific game
print()
print("=" * 50)
print("CHECKING SPECIFIC GAMES")
print("=" * 50)

# Find Duke game in training data
duke_training = [r for r in training if 'duke' in r['home_team'].lower() or 'duke' in r['away_team'].lower()][:3]
print("\nDuke games in TRAINING data:")
for g in duke_training:
    print(f"  {g['game_date']}: {g['away_team']} @ {g['home_team']} ({g['away_score']}-{g['home_score']})")

# Find Duke game in odds
duke_odds = [r for r in odds if 'duke' in r.get('home_team_canonical', '').lower() or 'duke' in r.get('away_team_canonical', '').lower()][:3]
print("\nDuke games in ODDS data:")
for g in duke_odds:
    date = g.get('game_date', g.get('commence_time', ''))[:10]
    print(f"  {date}: {g.get('away_team_canonical')} @ {g.get('home_team_canonical')} (spread: {g.get('spread')})")

# Find Duke game in H1
duke_h1 = [r for r in h1 if 'duke' in r['home_team'].lower() or 'duke' in r['away_team'].lower()][:3]
print("\nDuke games in H1 data:")
for g in duke_h1:
    print(f"  {g['date']}: {g['away_team']} @ {g['home_team']} (H1: {g['away_h1']}-{g['home_h1']})")
