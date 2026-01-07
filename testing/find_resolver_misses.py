"""Find exact mismatches and build missing mappings."""
import csv
import json
from collections import Counter

# Load resolver
with open('../services/prediction-service-python/training_data/team_aliases_db.json', 'r') as f:
    resolver_data = json.load(f)

def resolve(name):
    if not name:
        return name
    key = name.strip().lower()
    return resolver_data.get(key, name.strip())

# Load training data teams
with open('../services/prediction-service-python/training_data/training_data_with_odds.csv', 'r') as f:
    training = list(csv.DictReader(f))

training_teams = {}
for r in training:
    date = r['game_date'][:10]
    home = r['home_team'].strip()
    away = r['away_team'].strip()
    # Store normalized versions
    home_norm = resolve(home)
    away_norm = resolve(away)
    training_teams[(date, home_norm, away_norm)] = (home, away)

# Load odds teams
with open('data/historical_odds/odds_consolidated_canonical.csv', 'r') as f:
    odds = list(csv.DictReader(f))

# Find mismatches
unmatched_odds_teams = Counter()
unmatched_examples = []

for r in odds:
    date = r.get('game_date', r.get('commence_time', ''))[:10]
    home = r.get('home_team_canonical', r.get('home_team', '')).strip()
    away = r.get('away_team_canonical', r.get('away_team', '')).strip()
    
    home_norm = resolve(home)
    away_norm = resolve(away)
    
    if (date, home_norm, away_norm) not in training_teams:
        unmatched_odds_teams[home_norm] += 1
        unmatched_odds_teams[away_norm] += 1
        if len(unmatched_examples) < 50:
            unmatched_examples.append({
                'date': date,
                'home_odds': home,
                'away_odds': away,
                'home_norm': home_norm,
                'away_norm': away_norm
            })

print("Most common UNMATCHED odds teams:")
for team, count in unmatched_odds_teams.most_common(30):
    print(f"  {count:4d}: '{team}'")

print("\nLooking for these teams in training data...")
# Get all training team names (normalized)
training_norm_teams = set()
for r in training:
    training_norm_teams.add(resolve(r['home_team']))
    training_norm_teams.add(resolve(r['away_team']))

print(f"\nTraining teams: {len(training_norm_teams)}")

# Check which top unmatched teams exist in training
print("\nChecking if top unmatched odds teams exist in training:")
for team, count in unmatched_odds_teams.most_common(15):
    exists = team in training_norm_teams
    similar = [t for t in training_norm_teams if team.lower()[:5] in t.lower() or t.lower()[:5] in team.lower()][:3]
    print(f"  '{team}': {'✅ EXISTS' if exists else '❌ NOT FOUND'}")
    if not exists and similar:
        print(f"      Similar: {similar}")
