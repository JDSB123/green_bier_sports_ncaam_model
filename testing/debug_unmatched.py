"""Debug why 54% of odds games don't match scores."""
import csv
import os
import json
from collections import defaultdict

# Load resolver
with open('../services/prediction-service-python/training_data/team_aliases_db.json', 'r') as f:
    data = json.load(f)
resolver = {}
for alias, canonical in data.items():
    resolver[alias.lower().strip()] = canonical
    resolver[canonical.lower().strip()] = canonical

def normalize(name):
    if not name:
        return name
    return resolver.get(name.strip().lower(), name.strip())

# Load training data
with open('../services/prediction-service-python/training_data/training_data_with_odds.csv', 'r') as f:
    training = list(csv.DictReader(f))

# Load odds
with open('data/historical_odds/odds_consolidated_canonical.csv', 'r') as f:
    odds = list(csv.DictReader(f))

# Build score lookup
scores = set()
for r in training:
    date = r['game_date'][:10]
    home = normalize(r['home_team'])
    away = normalize(r['away_team'])
    scores.add((date, home, away))

print(f"Score games: {len(scores):,}")
print(f"Odds games: {len(odds):,}")

# Check 2023-24 odds games
season_2324 = [r for r in odds if r.get('game_date', r.get('commence_time', ''))[:4] in ('2023', '2024') and r.get('game_date', r.get('commence_time', ''))[5:7] in ('11', '12', '01', '02', '03', '04')]

print(f"\n2023-24 odds games: {len(season_2324):,}")

matched = 0
unmatched_samples = []
for r in season_2324:
    date = r.get('game_date', r.get('commence_time', ''))[:10]
    home = normalize(r.get('home_team_canonical', r.get('home_team', '')))
    away = normalize(r.get('away_team_canonical', r.get('away_team', '')))
    
    if (date, home, away) in scores:
        matched += 1
    else:
        if len(unmatched_samples) < 20:
            unmatched_samples.append((date, away, home))

print(f"Matched: {matched:,}")
print(f"Unmatched: {len(season_2324) - matched:,}")

print("\nSample UNMATCHED odds games:")
for date, away, home in unmatched_samples[:10]:
    print(f"  {date}: {away} @ {home}")
    
    # Try to find closest match in scores
    day_scores = [(d, h, a) for (d, h, a) in scores if d == date]
    if day_scores:
        print(f"    Scores on that day ({len(day_scores)}):")
        for d, h, a in day_scores[:3]:
            if home.lower()[:4] in h.lower() or away.lower()[:4] in a.lower():
                print(f"      {a} @ {h} <-- possible match?")

# Check if issue is date format
print("\n\nDate format check:")
print(f"Odds date sample: {odds[1000].get('game_date', odds[1000].get('commence_time', ''))[:10]}")
print(f"Training date sample: {training[1000]['game_date'][:10]}")
