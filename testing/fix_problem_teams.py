"""Fix resolver to match EXACTLY what training data uses."""
import json
import pandas as pd

resolver_path = '../services/prediction-service-python/training_data/team_aliases_db.json'
with open(resolver_path, 'r') as f:
    resolver = json.load(f)

# Load training data to find exact team names
training = pd.read_csv('../services/prediction-service-python/training_data/training_data_with_odds.csv')
games_all = pd.read_csv('data/historical/games_all.csv')

all_training_teams = set(training['home_team'].unique()) | set(training['away_team'].unique())
all_training_teams |= set(games_all['home_team'].unique()) | set(games_all['away_team'].unique())

print(f"Training has {len(all_training_teams)} unique teams")

# Count how often each team appears
from collections import Counter
team_counts = Counter()
for col in ['home_team', 'away_team']:
    team_counts.update(training[col].value_counts().to_dict())
    team_counts.update(games_all[col].value_counts().to_dict())

# For problem teams, find the MOST COMMON variant in training
problem_teams = {
    'fort wayne': ['Purdue Fort Wayne Mastodons', 'Fort Wayne', 'IPFW'],
    'loyola maryland': ['Loyola Maryland Greyhounds', 'Loyola Maryland'],
    'ut martin': ['UT Martin Skyhawks', 'UT Martin'],
    'miami fl': ['Miami Hurricanes', 'Miami (FL)'],
    'utrgv': ['UTRGV', 'UT Rio Grande Valley Vaqueros'],
    'little rock': ['Little Rock Trojans', 'UALR', 'Arkansas-Little Rock'],
    'mississippi valley': ['Mississippi Valley State Delta Devils', 'Miss. Valley St.'],
}

print("\nMost common variant for each problem team:")
for name, variants in problem_teams.items():
    counts = [(v, team_counts.get(v, 0)) for v in variants]
    counts.sort(key=lambda x: -x[1])
    best = counts[0][0]
    print(f"  {name}: {best} ({counts[0][1]} games) vs others: {counts[1:]}")

# Create correct mappings based on most common in training
final_fixes = {
    # Fort Wayne - Purdue Fort Wayne Mastodons is most common
    'fort wayne mastodons': 'Purdue Fort Wayne Mastodons',
    'fort wayne': 'Purdue Fort Wayne Mastodons',
    'ipfw': 'Purdue Fort Wayne Mastodons',
    'ipfw jaguars': 'Purdue Fort Wayne Mastodons',
    'purdue fort wayne': 'Purdue Fort Wayne Mastodons',
    'pfw': 'Purdue Fort Wayne Mastodons',
    
    # Loyola Maryland
    'loyola (md) greyhounds': 'Loyola Maryland Greyhounds',
    'loyola (md)': 'Loyola Maryland Greyhounds',
    'loyola md': 'Loyola Maryland Greyhounds',
    'loyola maryland': 'Loyola Maryland Greyhounds',
    'loyola-maryland': 'Loyola Maryland Greyhounds',
    
    # UT Martin - UT Martin Skyhawks is most common
    'tenn-martin skyhawks': 'UT Martin Skyhawks',
    'tenn-martin': 'UT Martin Skyhawks',
    'tennessee-martin': 'UT Martin Skyhawks',
    'tennessee martin': 'UT Martin Skyhawks',
    'ut martin': 'UT Martin Skyhawks',
    'tennessee-martin skyhawks': 'UT Martin Skyhawks',
    
    # Miami FL
    'miami hurricanes': 'Miami (FL)',
    'miami fl': 'Miami (FL)',
    
    # UTRGV
    'ut rio grande valley vaqueros': 'UTRGV',
    'ut rio grande valley': 'UTRGV',
    'texas-rio grande valley': 'UTRGV',
    
    # Arkansas Little Rock
    'arkansas-little rock trojans': 'Little Rock Trojans',
    'arkansas-little rock': 'Little Rock Trojans',
    'arkansas little rock': 'Little Rock Trojans',
    'ualr': 'Little Rock Trojans',
    'little rock': 'Little Rock Trojans',
    
    # Mississippi Valley State
    'miss valley st delta devils': 'Mississippi Valley State Delta Devils',
    'miss valley state': 'Mississippi Valley State Delta Devils',
    'miss valley st': 'Mississippi Valley State Delta Devils',
    'mississippi valley state': 'Mississippi Valley State Delta Devils',
    'miss. valley st.': 'Mississippi Valley State Delta Devils',
    'mvsu': 'Mississippi Valley State Delta Devils',
    'mvsu delta devils': 'Mississippi Valley State Delta Devils',
}

for alias, canonical in final_fixes.items():
    resolver[alias.lower()] = canonical

print(f"\nUpdated: {len(resolver)} mappings")

# Save
with open(resolver_path, 'w') as f:
    json.dump(resolver, f, indent=2, sort_keys=True)

print("Saved!")
