"""Check team name resolver gaps."""
import csv
import json

# Load resolver
with open('../services/prediction-service-python/training_data/team_aliases_db.json', 'r') as f:
    data = json.load(f)

# Check specific teams that failed to match
tests = ['N.C. State', 'NC State', 'North Carolina State', 'NCSU', 
         'Penn St.', 'Penn State', 
         "Saint Joseph's", 'Saint Josephs', "St. Joseph's",
         'Chicago St.', 'Chicago State',
         'The Citadel', 'Citadel',
         'C. Connecticut', 'Central Connecticut', 'Central Connecticut St.',
         'UMBC', 'Maryland-Baltimore County']

print("Resolver mappings:")
for t in tests:
    canonical = data.get(t.lower(), 'NOT FOUND')
    print(f"  '{t}' -> {canonical}")

print()

# Load training to see actual team names
with open('../services/prediction-service-python/training_data/training_data_with_odds.csv', 'r') as f:
    training = list(csv.DictReader(f))

# Get unique team names from training
training_teams = set()
for r in training:
    training_teams.add(r['home_team'])
    training_teams.add(r['away_team'])

print(f"Unique teams in training data: {len(training_teams)}")

# Find NC State
nc_matches = [t for t in training_teams if 'nc' in t.lower() or 'n.c' in t.lower()]
print("\nTeams with 'NC' in training data:")
for t in sorted(nc_matches):
    print(f"  '{t}'")

# Find Saint Joseph's
sj_matches = [t for t in training_teams if 'joseph' in t.lower()]
print("\nTeams with 'Joseph' in training data:")
for t in sorted(sj_matches):
    print(f"  '{t}'")

# Find Penn State
penn_matches = [t for t in training_teams if 'penn' in t.lower()]
print("\nTeams with 'Penn' in training data:")
for t in sorted(penn_matches):
    print(f"  '{t}'")
