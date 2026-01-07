"""Fix resolver with correct training data team names."""
import csv
import json

# Load training data
with open('../services/prediction-service-python/training_data/training_data_with_odds.csv', 'r') as f:
    training = list(csv.DictReader(f))

training_teams = set()
for r in training:
    training_teams.add(r['home_team'].strip())
    training_teams.add(r['away_team'].strip())

# Also games_all
with open('data/historical/games_all.csv', 'r') as f:
    games_all = list(csv.DictReader(f))

for r in games_all:
    training_teams.add(r['home_team'].strip())
    training_teams.add(r['away_team'].strip())

# Load resolver
resolver_path = '../services/prediction-service-python/training_data/team_aliases_db.json'
with open(resolver_path, 'r') as f:
    resolver = json.load(f)

print(f"Original: {len(resolver)} mappings")

# CORRECT mappings based on actual training data
correct_mappings = {
    # State abbreviations
    "washington st.": "Washington State",
    "oregon st.": "Oregon State",
    "montana st.": "Montana State",
    "morehead st.": "Morehead State",
    "alabama st.": "Alabama State",
    "jackson st.": "Jackson State",
    "jacksonville st.": "Jacksonville State",
    "southeast missouri st.": "Southeast Missouri State",
    "weber st.": "Weber State",
    "alcorn st.": "Alcorn State",
    "norfolk st.": "Norfolk State",
    "coppin st.": "Coppin State",
    "mississippi valley st.": "Mississippi Valley State",
    "long beach st.": "Long Beach State",
    "s.c. st.": "South Carolina State",
    "fresno st.": "Fresno State",
    "boise st.": "Boise State",
    "colorado st.": "Colorado State",
    "san diego st.": "San Diego State",
    "san jose st.": "San Jose State",
    "utah st.": "Utah State",
    "kent st.": "Kent State",
    "ball st.": "Ball State",
    "iowa st.": "Iowa State",
    "kansas st.": "Kansas State",
    "oklahoma st.": "Oklahoma State",
    "michigan st.": "Michigan State",
    "ohio st.": "Ohio State",
    "penn st.": "Penn State",
    "murray st.": "Murray State",
    "tennessee st.": "Tennessee State",
    "appalachian st.": "Appalachian State",
    "georgia st.": "Georgia State",
    "kennesaw st.": "Kennesaw State",
    "idaho st.": "Idaho State",
    "portland st.": "Portland State",
    "sacramento st.": "Sacramento State",
    "tarleton st.": "Tarleton",
    "mcneese st.": "McNeese State",
    "nicholls st.": "Nicholls State",
    "northwestern st.": "Northwestern St.",
    "texas st.": "Texas State",
    "chicago st.": "Chicago State",
    "grambling st.": "Grambling St.",
    "arkansas st.": "Arkansas State",
    "cleveland st.": "Cleveland State",
    "youngstown st.": "Youngstown State",
    "wright st.": "Wright State",
    "wichita st.": "Wichita State",
    "missouri st.": "Missouri State",
    "illinois st.": "Illinois State",
    "indiana st.": "Indiana State",
    
    # UNC/NC variations
    "unc greensboro": "NC Greensboro",
    
    # ETSU - training uses "East Tennessee St"
    "etsu": "East Tennessee St",
    "east tennessee st.": "East Tennessee St",
    "east tennessee state": "East Tennessee St",
    
    # Miami
    "miami oh": "Miami (Ohio)",
    "miami (oh)": "Miami (Ohio)",
    
    # FAU
    "fau": "Florida Atlantic",
    "florida atlantic": "Florida Atlantic",
    
    # Chattanooga
    "chattanooga": "Chattanooga",
    "ut chattanooga": "Chattanooga",
    
    # Saint/St variations
    "saint mary's": "Saint Mary's",
    "st. mary's": "Saint Mary's",
    "saint mary's (ca)": "Saint Mary's",
    "saint joseph's": "Saint Josephs",
    "st. joseph's": "Saint Josephs",
    "saint louis": "St. Louis",
    "st. louis": "St. Louis",
    "st. john's": "St. John's",
    
    # Louisiana
    "louisiana": "Louisiana Lafayette",
    "louisiana-lafayette": "Louisiana Lafayette",
    "ul lafayette": "Louisiana Lafayette",
    "southeastern louisiana": "SE Louisiana",
    "se louisiana": "SE Louisiana",
    
    # Wisconsin schools
    "milwaukee": "Wisc. Milwaukee",
    "uw-milwaukee": "Wisc. Milwaukee",
    "green bay": "Wisc. Green Bay",
    "uw-green bay": "Wisc. Green Bay",
    
    # Eastern Washington
    "eastern washington": "East. Washington",
    "e. washington": "East. Washington",
    
    # Arkansas Pine Bluff - check what training has
    "arkansas pine bluff": "Arkansas-Pine Bluff",
    "arkansas-pine bluff": "Arkansas-Pine Bluff",
    
    # North Carolina A&T
    "north carolina a&t": "North Carolina A&T",
    "n.c. a&t": "North Carolina A&T",
    
    # Little Rock
    "little rock": "Little Rock",
    "ualr": "Little Rock",
    "arkansas-little rock": "Little Rock",
}

# Apply corrections
for alias, canonical in correct_mappings.items():
    resolver[alias] = canonical

# Verify all canonical names exist
print("\nVerifying all mappings...")
missing = []
for alias, canonical in correct_mappings.items():
    if canonical not in training_teams:
        # Try to find it
        matches = [t for t in training_teams if canonical.lower()[:8] in t.lower() or t.lower()[:8] in canonical.lower()]
        if matches:
            print(f"  {canonical} -> using {matches[0]}")
            resolver[alias] = matches[0]
        else:
            print(f"  ❌ {canonical} NOT FOUND")
            missing.append(canonical)

print(f"\nMissing teams that need manual lookup: {len(missing)}")
print(f"Final: {len(resolver)} mappings")

# Save
with open(resolver_path, 'w') as f:
    json.dump(resolver, f, indent=2, sort_keys=True)

print(f"Saved to {resolver_path}")
