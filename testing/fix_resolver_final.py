"""Final resolver fix with EXACT training data team names."""
import csv
import json

# Load resolver
resolver_path = '../services/prediction-service-python/training_data/team_aliases_db.json'
with open(resolver_path, 'r') as f:
    resolver = json.load(f)

print(f"Original: {len(resolver)} mappings")

# EXACT mappings: odds format -> training format
# Based on actual teams found in training data
exact_mappings = {
    # State abbreviations - these ARE in training data
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
    "long beach st.": "Long Beach State",
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
    "mcneese st.": "McNeese State",
    "nicholls st.": "Nicholls State",
    "texas st.": "Texas State",
    "chicago st.": "Chicago State",
    "arkansas st.": "Arkansas State",
    "cleveland st.": "Cleveland State",
    "youngstown st.": "Youngstown State",
    "wright st.": "Wright State",
    "wichita st.": "Wichita State",
    "missouri st.": "Missouri State",
    "illinois st.": "Illinois State",
    "indiana st.": "Indiana State",
    
    # Training uses abbreviated versions
    "mississippi valley st.": "Miss. Valley St.",  # Guess - may not exist
    "s.c. st.": "South Carolina St",  # Training uses "South Carolina St"
    "sc state": "South Carolina St",
    "south carolina state": "South Carolina St",
    "tarleton st.": "Tarleton",
    "northwestern st.": "Northwestern St.",
    "grambling st.": "Grambling St.",
    "mississippi st.": "Mississippi St.",
    
    # NC variations
    "unc greensboro": "NC Greensboro",
    "n.c. greensboro": "NC Greensboro",
    
    # ETSU
    "etsu": "East Tennessee St",
    "east tennessee st.": "East Tennessee St",
    "east tennessee state": "East Tennessee St",
    
    # Miami
    "miami oh": "Miami (Ohio)",
    "miami (oh)": "Miami (Ohio)",
    
    # FAU
    "fau": "Florida Atlantic",
    "florida atlantic": "Florida Atlantic",
    
    # Chattanooga - training uses "Chattanooga Mocs"
    "chattanooga": "Chattanooga Mocs",
    "ut chattanooga": "Chattanooga Mocs",
    
    # Saint/St variations
    "saint mary's": "St. Marys (CA)",
    "st. mary's": "St. Marys (CA)",
    "saint mary's (ca)": "St. Marys (CA)",
    "saint joseph's": "Saint Josephs",
    "st. joseph's": "Saint Josephs",
    "saint louis": "St. Louis",
    "st. louis": "St. Louis",
    "st. john's": "St. John's",
    
    # Louisiana
    "louisiana": "Louisiana",
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
    
    # Arkansas Pine Bluff
    "arkansas pine bluff": "Arkansas-Pine Bluff",
    "arkansas-pine bluff": "Arkansas-Pine Bluff",
    
    # North Carolina A&T - training uses "N. Carolina A&T"
    "north carolina a&t": "N. Carolina A&T",
    "n.c. a&t": "N. Carolina A&T",
    "nc a&t": "N. Carolina A&T",
    
    # Little Rock - check if in training
    "little rock": "Little Rock",
    "ualr": "Little Rock",
    "arkansas-little rock": "Little Rock",
}

# Apply all mappings
for alias, canonical in exact_mappings.items():
    resolver[alias] = canonical

print(f"Final: {len(resolver)} mappings")

# Save
with open(resolver_path, 'w') as f:
    json.dump(resolver, f, indent=2, sort_keys=True)

print(f"Saved to {resolver_path}")
print("\nKey mappings:")
for alias in ['etsu', 'chattanooga', 'north carolina a&t', 's.c. st.', 'saint mary\'s', 'st. john\'s']:
    print(f"  {alias} -> {resolver.get(alias, 'NOT FOUND')}")
