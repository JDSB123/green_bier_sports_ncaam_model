"""Add missing team name mappings to resolver and rebuild backtest data."""
import csv
import json
import os
from collections import defaultdict

# Load existing resolver
resolver_path = '../services/prediction-service-python/training_data/team_aliases_db.json'
with open(resolver_path, 'r') as f:
    resolver = json.load(f)

print(f"Original resolver: {len(resolver)} mappings")

# Load training data to get authoritative team names
with open('../services/prediction-service-python/training_data/training_data_with_odds.csv', 'r') as f:
    training = list(csv.DictReader(f))

training_teams = set()
for r in training:
    training_teams.add(r['home_team'].strip())
    training_teams.add(r['away_team'].strip())

print(f"Training data teams: {len(training_teams)}")

# Load games_all.csv for more team names
with open('data/historical/games_all.csv', 'r') as f:
    games_all = list(csv.DictReader(f))

for r in games_all:
    training_teams.add(r['home_team'].strip())
    training_teams.add(r['away_team'].strip())

print(f"All score data teams: {len(training_teams)}")

# Add new mappings for common odds formats -> training formats
new_mappings = {
    # State abbreviations
    "st. john's": "St. John's",
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
    "s.c. state": "South Carolina State",
    "sc state": "South Carolina State",
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
    "troy st.": "Troy",
    "idaho st.": "Idaho State",
    "portland st.": "Portland State",
    "sacramento st.": "Sacramento State",
    "cal st. bakersfield": "Cal State Bakersfield",
    "cal st. fullerton": "Cal State Fullerton",
    "cal st. northridge": "Cal State Northridge",
    "tarleton st.": "Tarleton State",
    "mcneese st.": "McNeese State",
    "nicholls st.": "Nicholls State",
    "northwestern st.": "Northwestern State",
    "stephen f. austin st.": "Stephen F. Austin",
    "texas st.": "Texas State",
    "chicago st.": "Chicago State",
    "grambling st.": "Grambling State",
    "prairie view a&m st.": "Prairie View A&M",
    "texas southern st.": "Texas Southern",
    "arkansas st.": "Arkansas State",
    "cleveland st.": "Cleveland State",
    "youngstown st.": "Youngstown State",
    "wright st.": "Wright State",
    "wichita st.": "Wichita State",
    "missouri st.": "Missouri State",
    "illinois st.": "Illinois State",
    "indiana st.": "Indiana State",
    "bowling green st.": "Bowling Green",
    "n.c. state": "NC State",
    "north carolina st.": "NC State",
    "n.c. a&t": "North Carolina A&T",
    
    # Saint variations
    "saint mary's": "Saint Mary's",
    "st. mary's": "Saint Mary's",
    "saint joseph's": "Saint Josephs",
    "st. joseph's": "Saint Josephs",
    "saint josephs": "Saint Josephs",
    "saint louis": "Saint Louis",
    "st. louis": "Saint Louis",
    "saint peter's": "Saint Peter's",
    "st. peter's": "Saint Peter's",
    "saint francis": "Saint Francis",
    "st. francis (pa)": "St. Francis (PA)",
    "st. bonaventure": "St. Bonaventure",
    "saint bonaventure": "St. Bonaventure",
    
    # UNC/NC variations
    "unc greensboro": "NC Greensboro",
    "unc wilmington": "NC Wilmington",
    "unc asheville": "UNC Asheville",
    
    # Common abbreviations
    "etsu": "East Tennessee State",
    "east tennessee st.": "East Tennessee State",
    "fau": "Florida Atlantic",
    "florida atlantic": "Florida Atlantic",
    "fiu": "Florida International",
    "florida international": "Florida International",
    "fgcu": "Florida Gulf Coast",
    "ucf": "UCF",
    "u.c.f.": "UCF",
    "uab": "UAB",
    "utep": "UTEP",
    "utsa": "UTSA",
    "unlv": "UNLV",
    "umbc": "UMBC",
    "vcu": "VCU",
    "smu": "SMU",
    "lsu": "LSU",
    "tcu": "TCU",
    "byu": "BYU",
    "usc": "USC",
    "ucla": "UCLA",
    
    # Miami
    "miami oh": "Miami (Ohio)",
    "miami (oh)": "Miami (Ohio)",
    "miami-ohio": "Miami (Ohio)",
    "miami fl": "Miami FL",
    "miami (fl)": "Miami FL",
    
    # Louisiana
    "louisiana": "Louisiana",
    "louisiana-lafayette": "Louisiana",
    "ul lafayette": "Louisiana",
    "louisiana-monroe": "Louisiana Monroe",
    "ul monroe": "Louisiana Monroe",
    "southeastern louisiana": "SE Louisiana",
    "se louisiana": "SE Louisiana",
    
    # Little Rock
    "little rock": "Little Rock",
    "ualr": "Little Rock",
    "arkansas-little rock": "Little Rock",
    
    # Chattanooga
    "chattanooga": "Chattanooga",
    "ut chattanooga": "Chattanooga",
    
    # Milwaukee
    "milwaukee": "Milwaukee",
    "uw-milwaukee": "Milwaukee",
    "wisconsin-milwaukee": "Milwaukee",
    
    # Eastern Washington
    "eastern washington": "Eastern Washington",
    "ewu": "Eastern Washington",
    
    # Arkansas Pine Bluff
    "arkansas pine bluff": "Arkansas-Pine Bluff",
    "arkansas-pine bluff": "Arkansas-Pine Bluff",
    "uapb": "Arkansas-Pine Bluff",
    
    # The Citadel
    "the citadel": "The Citadel",
    "citadel": "The Citadel",
    
    # Other common variations
    "bowling green": "Bowling Green",
    "central connecticut": "Central Connecticut",
    "c. connecticut": "Central Connecticut",
    "northern iowa": "Northern Iowa",
    "southern illinois": "Southern Illinois",
    "northern illinois": "Northern Illinois",
    "western kentucky": "Western Kentucky",
    "eastern kentucky": "Eastern Kentucky",
    "western michigan": "Western Michigan",
    "eastern michigan": "Eastern Michigan",
    "central michigan": "Central Michigan",
    "northern arizona": "Northern Arizona",
    "southern utah": "Southern Utah",
}

# Add mappings
added = 0
for alias, canonical in new_mappings.items():
    if alias.lower() not in resolver:
        resolver[alias.lower()] = canonical
        added += 1

print(f"Added {added} new mappings")
print(f"New resolver size: {len(resolver)}")

# Save updated resolver
with open(resolver_path, 'w') as f:
    json.dump(resolver, f, indent=2, sort_keys=True)

print(f"Saved to {resolver_path}")
