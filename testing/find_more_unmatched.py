"""Find remaining unmatched teams and add to resolver."""
import csv
import json
from collections import Counter

# Load current resolver
with open('../services/prediction-service-python/training_data/team_aliases_db.json', 'r') as f:
    resolver = json.load(f)

def resolve(name):
    if not name:
        return name
    return resolver.get(name.strip().lower(), name.strip())

# Load training data
with open('../services/prediction-service-python/training_data/training_data_with_odds.csv', 'r') as f:
    training = list(csv.DictReader(f))

with open('data/historical/games_all.csv', 'r') as f:
    games_all = list(csv.DictReader(f))

# Build score lookup
scores = set()
for r in training:
    date = r['game_date'][:10]
    home = resolve(r['home_team'])
    away = resolve(r['away_team'])
    scores.add((date, home, away))

for r in games_all:
    date = r['date'][:10]
    home = resolve(r['home_team'])
    away = resolve(r['away_team'])
    scores.add((date, home, away))

# Load odds
with open('data/historical_odds/odds_consolidated_canonical.csv', 'r') as f:
    odds = list(csv.DictReader(f))

# Find unmatched
unmatched_teams = Counter()
unmatched_examples = []

for r in odds:
    date = r.get('game_date', r.get('commence_time', ''))[:10]
    home = resolve(r.get('home_team_canonical', r.get('home_team', '')))
    away = resolve(r.get('away_team_canonical', r.get('away_team', '')))
    
    if (date, home, away) not in scores:
        unmatched_teams[home] += 1
        unmatched_teams[away] += 1
        if len(unmatched_examples) < 30:
            unmatched_examples.append((date, away, home))

print("Top 30 STILL UNMATCHED odds teams:")
for team, count in unmatched_teams.most_common(30):
    print(f"  {count:4d}: '{team}'")

# Get all training teams for matching
training_teams = set()
for r in training:
    training_teams.add(r['home_team'].strip())
    training_teams.add(r['away_team'].strip())
for r in games_all:
    training_teams.add(r['home_team'].strip())
    training_teams.add(r['away_team'].strip())

print(f"\nTraining teams: {len(training_teams)}")

# Try to find matches for top unmatched
print("\nSuggested mappings:")
new_mappings = {}
for team, count in unmatched_teams.most_common(30):
    # Find similar in training
    team_lower = team.lower()
    matches = []
    
    # Try first word match
    first_word = team_lower.split()[0] if team_lower.split() else team_lower
    for t in training_teams:
        t_lower = t.lower()
        if first_word in t_lower or t_lower.split()[0] in team_lower:
            matches.append(t)
    
    if len(matches) == 1:
        print(f"  '{team.lower()}' -> '{matches[0]}'  # auto")
        new_mappings[team.lower()] = matches[0]
    elif matches:
        print(f"  '{team}' -> options: {matches[:3]}")
