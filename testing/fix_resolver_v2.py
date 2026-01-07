"""Fix resolver to map odds formats to training data formats."""
import csv
import json

# Load training data to get canonical names
with open('../services/prediction-service-python/training_data/training_data_with_odds.csv', 'r') as f:
    training = list(csv.DictReader(f))

training_teams = set()
for r in training:
    training_teams.add(r['home_team'].strip())
    training_teams.add(r['away_team'].strip())

# Also load games_all
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
print(f"Training teams: {len(training_teams)}")

# These need to map odds format -> training format
corrections = {
    # State abbreviations -> State full
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
    "tarleton st.": "Tarleton State",
    "mcneese st.": "McNeese State",
    "nicholls st.": "Nicholls State",
    "northwestern st.": "Northwestern State",
    "texas st.": "Texas State",
    "chicago st.": "Chicago State",
    "grambling st.": "Grambling State",
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
    
    # ETSU
    "etsu": "East Tennessee State",
    "east tennessee st.": "East Tennessee State",
    
    # Miami
    "miami oh": "Miami (Ohio)",
    "miami (oh)": "Miami (Ohio)",
    
    # FAU
    "fau": "Florida Atlantic",
    
    # Chattanooga - check what training uses
    "chattanooga": "Chattanooga",
    
    # Saint variations - check training
    "saint mary's": "Saint Mary's",
    "st. mary's": "Saint Mary's",
    "saint joseph's": "Saint Josephs",
    "st. joseph's": "Saint Josephs",
    "saint louis": "Saint Louis",
    "st. louis": "Saint Louis",
    
    # Louisiana
    "louisiana": "Louisiana",
    "southeastern louisiana": "SE Louisiana",
    
    # Milwaukee
    "milwaukee": "Milwaukee",
    
    # Eastern Washington
    "eastern washington": "East. Washington",
    "e. washington": "East. Washington",
    
    # Arkansas Pine Bluff
    "arkansas pine bluff": "Arkansas-Pine Bluff",
    
    # Green Bay
    "green bay": "Green Bay",
    
    # North Carolina A&T
    "north carolina a&t": "North Carolina A&T",
    "n.c. a&t": "North Carolina A&T",
    
    # Little Rock
    "little rock": "Little Rock",
    
    # St. John's 
    "st. john's": "St. John's",
}

# Verify each canonical exists in training
print("\nVerifying corrections against training data:")
missing = []
for alias, canonical in corrections.items():
    if canonical not in training_teams:
        # Find closest match
        close = [t for t in training_teams if canonical.lower()[:5] in t.lower() or t.lower()[:5] in canonical.lower()][:3]
        print(f"  ❌ '{canonical}' not in training. Similar: {close}")
        missing.append((alias, canonical, close))
    else:
        resolver[alias] = canonical

# Handle missing ones
for alias, canonical, close in missing:
    if close:
        # Use first close match
        resolver[alias] = close[0]
        print(f"  → Mapping '{alias}' to '{close[0]}'")

print(f"\nFinal: {len(resolver)} mappings")

# Save
with open(resolver_path, 'w') as f:
    json.dump(resolver, f, indent=2, sort_keys=True)

print(f"Saved to {resolver_path}")
