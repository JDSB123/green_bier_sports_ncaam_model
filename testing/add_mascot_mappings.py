"""Add mascot-stripped mappings to resolver."""
import json
import re

resolver_path = '../services/prediction-service-python/training_data/team_aliases_db.json'
with open(resolver_path, 'r') as f:
    resolver = json.load(f)

print(f"Original: {len(resolver)} mappings")

# List of common mascot names to strip
mascots = [
    'Buccaneers', 'Musketeers', 'RedHawks', 'Catamounts', 'Tigers', 'Wildcats',
    'Terrapins', 'Friars', 'Fighting Illini', 'Buckeyes', 'Gaels', 'Braves',
    'Wolf Pack', 'Cougars', 'Hawkeyes', 'Mavericks', 'Cardinals', 'Wolverines',
    'Hilltoppers', 'Bulldogs', 'Volunteers', 'Terriers', 'Ducks', 'Seminoles',
    'Bruins', 'Boilermakers', 'Horned Frogs', 'Big Red', 'Spartans', 'Mastodons',
    'Flames', 'Eagles', 'Bears', 'Hoosiers', 'Cavaliers', 'Minutemen', 'Mountaineers',
    'Jayhawks', 'Sooners', 'Cowboys', 'Longhorns', 'Red Raiders', 'Cyclones',
    'Razorbacks', 'Panthers', 'Yellow Jackets', 'Crimson Tide', 'Demon Deacons',
    'Blue Devils', 'Tar Heels', 'Wolfpack', 'Orange', 'Hokies', 'Hurricanes',
    'Nittany Lions', 'Scarlet Knights', 'Terrapins', 'Badgers', 'Gophers',
    'Cornhuskers', 'Hawkeyes', 'Huskers', 'Aggies', 'Rams', 'Aztecs', 'Ramblers',
    'Gamecocks', 'Racers', 'Sun Devils', 'Shockers', 'Anteaters', 'Grizzlies',
    'Redbirds', 'Owls', 'Golden Flashes', 'Sycamores', 'Penguins', 'Raiders',
    'Bobcats', 'Bengals', 'Vikings', 'Beach', 'Hornets', 'Colonels', 'Redhawks',
    'Bearkats', 'Lumberjacks', 'Peacocks', 'Bonnies', 'Flyers', 'Explorers',
    'Billikens', 'Zags', 'Pilots', 'Waves', 'Toreros', 'Dons', 'Broncos',
    'Bluejays', 'Golden Eagles', 'Red Storm', 'Friars', 'Huskies', 'Hoyas',
    'Pirates', 'Spiders', 'Dukes', 'Golden Hurricanes', 'Mean Green', 'Roadrunners',
    'Monarchs', 'Thundering Herd', 'Rockets', 'Redhawks', 'Bulls', 'Falcons',
    'Chippewas', 'Broncos', 'Huskies', 'Flames', 'Phoenix', 'Leathernecks',
    'Fighting Hawks', 'Bison', 'Jackrabbits', 'Coyotes', 'Kangaroos', 'Ospreys',
    'Dolphins', 'Hatters', 'Paladins', 'Catamounts', 'Chanticleers', 'Trojans',
    'Highlanders', 'Matadors', 'Gauchos', 'Mustangs', 'Titans', '49ers',
    'Rainbow Warriors', 'Vandals', 'Seawolves', 'Great Danes', 'River Hawks',
    'Retrievers', 'Blue Hens', 'Pride', 'Beavers', 'Jaguars', 'Jaspers',
    'Stags', 'Gaels', 'Lions', 'Leopards', 'Engineers', 'Saints', 'Hawks',
    'Skyhawks', 'Governors', 'Colonels', 'Delta Devils', 'Prairie View A&M Panthers',
    'Rattlers', 'Maroon Tigers', 'Lady Tigers', 'Jaguars', 'Hornets', 'Braves',
    'Express', 'Texans', 'Pioneers', 'Battlin\' Bishops', 'Battling Bishops'
]

# Create pattern
mascot_pattern = r'\s+(' + '|'.join(re.escape(m) for m in mascots) + r')$'

# State abbreviations to full
state_abbrevs = {
    'St': 'State',
    'St.': 'State',
}

def normalize_for_match(name):
    """Strip mascot and expand abbreviations."""
    # Strip mascot
    base = re.sub(mascot_pattern, '', name, flags=re.IGNORECASE).strip()
    
    # Expand St/St. to State
    for abbr, full in state_abbrevs.items():
        if base.endswith(' ' + abbr):
            base = base[:-len(abbr)] + full
    
    return base

# Get all unique team names from odds file
import pandas as pd
odds = pd.read_csv('data/historical_odds/odds_consolidated_canonical.csv')
games_all = pd.read_csv('data/historical/games_all.csv')

all_teams = set(odds['home_team'].unique()) | set(odds['away_team'].unique())
all_teams |= set(games_all['home_team'].unique()) | set(games_all['away_team'].unique())

print(f"Found {len(all_teams)} unique team names")

# Add mappings
added = 0
for team in all_teams:
    base = normalize_for_match(team)
    if base.lower() != team.lower():
        # Map the full (with mascot) to the base
        # Also map the base to itself (canonical)
        resolver[team.lower()] = base
        resolver[base.lower()] = base
        added += 1

# Add specific abbreviation expansions
manual = {
    # With mascots
    'kansas st wildcats': 'Kansas State',
    'michigan st spartans': 'Michigan State',
    'ohio st buckeyes': 'Ohio State',
    'penn st nittany lions': 'Penn State',
    'iowa st cyclones': 'Iowa State',
    'oklahoma st cowboys': 'Oklahoma State',
    'oregon st beavers': 'Oregon State',
    'washington st cougars': 'Washington State',
    'colorado st rams': 'Colorado State',
    'san diego st aztecs': 'San Diego State',
    'boise st broncos': 'Boise State',
    'fresno st bulldogs': 'Fresno State',
    'utah st aggies': 'Utah State',
    'arizona st sun devils': 'Arizona State',
    'florida st seminoles': 'Florida State',
    'murray st racers': 'Murray State',
    'wichita st shockers': 'Wichita State',
    'indiana st sycamores': 'Indiana State',
    'illinois st redbirds': 'Illinois State',
    'morehead st eagles': 'Morehead State',
    'jacksonville st gamecocks': 'Jacksonville State',
    'jackson st tigers': 'Jackson State',
    'grambling st tigers': 'Grambling State',
    # Without mascots (St. abbreviation)
    'kansas st.': 'Kansas State',
    'michigan st.': 'Michigan State',
    'ohio st.': 'Ohio State',
    'penn st.': 'Penn State',
    'iowa st.': 'Iowa State',
    'oklahoma st.': 'Oklahoma State',
    'oregon st.': 'Oregon State',
    'washington st.': 'Washington State',
    'colorado st.': 'Colorado State',
    'san diego st.': 'San Diego State',
    'boise st.': 'Boise State',
    'fresno st.': 'Fresno State',
    'utah st.': 'Utah State',
    'arizona st.': 'Arizona State',
    'florida st.': 'Florida State',
    'murray st.': 'Murray State',
    'wichita st.': 'Wichita State',
    'indiana st.': 'Indiana State',
    'illinois st.': 'Illinois State',
    'morehead st.': 'Morehead State',
    'jacksonville st.': 'Jacksonville State',
    'jackson st.': 'Jackson State',
    'grambling st.': 'Grambling State',
    'east tennessee st.': 'East Tennessee State',
    'east tennessee st buccaneers': 'East Tennessee State',
    'east tennessee state buccaneers': 'East Tennessee State',
    # Saint variations
    "saint mary's gaels": "Saint Mary's",
    "st. mary's gaels": "Saint Mary's",
    "saint mary's": "Saint Mary's",
    "st. mary's": "Saint Mary's",
    "saint john's": "St. John's",
    "st. john's red storm": "St. John's",
    "saint joseph's": "Saint Joseph's",
    "st. joseph's": "Saint Joseph's",
    "saint joseph's hawks": "Saint Joseph's",
    "saint louis billikens": "Saint Louis",
    "saint louis": "Saint Louis",
    "st. louis": "Saint Louis",
    # Other specific fixes
    'loyola (chi) ramblers': 'Loyola Chicago',
    'loyola-chicago ramblers': 'Loyola Chicago',
    'loyola chicago': 'Loyola Chicago',
    'siu-edwardsville cougars': 'SIU Edwardsville',
    'siu edwardsville': 'SIU Edwardsville',
    'unc greensboro spartans': 'UNC Greensboro',
    'unc greensboro': 'UNC Greensboro',
    'unc wilmington seahawks': 'UNC Wilmington',
    'unc wilmington': 'UNC Wilmington',
    'north dakota st bison': 'North Dakota State',
    'north dakota state bison': 'North Dakota State',
    'north dakota state': 'North Dakota State',
    'north dakota st.': 'North Dakota State',
    'south dakota st jackrabbits': 'South Dakota State',
    'south dakota state jackrabbits': 'South Dakota State',
    'south dakota state': 'South Dakota State',
    'south dakota st.': 'South Dakota State',
    'miami (oh) redhawks': 'Miami (OH)',
    'miami (fl) hurricanes': 'Miami',
    'ut-arlington mavericks': 'UT Arlington',
    'ut arlington': 'UT Arlington',
    'uc irvine anteaters': 'UC Irvine',
    'uc irvine': 'UC Irvine',
    'uc riverside highlanders': 'UC Riverside',
    'uc riverside': 'UC Riverside',
    'uc davis aggies': 'UC Davis',
    'uc davis': 'UC Davis',
    'uc santa barbara gauchos': 'UC Santa Barbara',
    'uc santa barbara': 'UC Santa Barbara',
    'uc san diego tritons': 'UC San Diego',
    'uc san diego': 'UC San Diego',
    'southeast missouri st redhawks': 'Southeast Missouri State',
    'southeast missouri state redhawks': 'Southeast Missouri State',
    'southeast missouri state': 'Southeast Missouri State',
    'southeast missouri st.': 'Southeast Missouri State',
    'california golden bears': 'California',
    'stanford cardinal': 'Stanford',
    'northern iowa panthers': 'Northern Iowa',
    'northern iowa': 'Northern Iowa',
    'uni': 'Northern Iowa',
    'north carolina central eagles': 'North Carolina Central',
    'north carolina a&t aggies': 'North Carolina A&T',
    # Mississippi
    'mississippi st bulldogs': 'Mississippi State',
    'mississippi state bulldogs': 'Mississippi State',
    'mississippi state': 'Mississippi State',
    'mississippi st.': 'Mississippi State',
    'miss. st.': 'Mississippi State',
    'mississippi valley st.': 'Mississippi Valley State',
    'miss. valley st.': 'Mississippi Valley State',
    'mississippi valley state delta devils': 'Mississippi Valley State',
    # Others
    'north carolina st wolfpack': 'NC State',
    'nc state wolfpack': 'NC State',
    'north carolina tar heels': 'North Carolina',
    'montana grizzlies': 'Montana',
    'montana state bobcats': 'Montana State',
    'alcorn st braves': 'Alcorn State',
    'alcorn state braves': 'Alcorn State',
    'alabama st hornets': 'Alabama State',
    'alabama state hornets': 'Alabama State',
    'tennessee st tigers': 'Tennessee State',
    'tennessee state tigers': 'Tennessee State',
    'norfolk st spartans': 'Norfolk State',
    'norfolk state spartans': 'Norfolk State',
    'coppin st eagles': 'Coppin State',
    'coppin state eagles': 'Coppin State',
    'morgan st bears': 'Morgan State',
    'morgan state bears': 'Morgan State',
    'portland st vikings': 'Portland State',
    'portland state vikings': 'Portland State',
    'weber st wildcats': 'Weber State',
    'weber state wildcats': 'Weber State',
    'sacramento st hornets': 'Sacramento State',
    'sacramento state hornets': 'Sacramento State',
    'mcneese st cowboys': 'McNeese State',
    'mcneese state cowboys': 'McNeese State',
    'nicholls st colonels': 'Nicholls State',
    'nicholls state colonels': 'Nicholls State',
    'arkansas st red wolves': 'Arkansas State',
    'arkansas state red wolves': 'Arkansas State',
    'georgia st panthers': 'Georgia State',
    'georgia state panthers': 'Georgia State',
    'texas st bobcats': 'Texas State',
    'texas state bobcats': 'Texas State',
    'kent st golden flashes': 'Kent State',
    'kent state golden flashes': 'Kent State',
    'ball st cardinals': 'Ball State',
    'ball state cardinals': 'Ball State',
    'cleveland st vikings': 'Cleveland State',
    'cleveland state vikings': 'Cleveland State',
    'youngstown st penguins': 'Youngstown State',
    'youngstown state penguins': 'Youngstown State',
    'wright st raiders': 'Wright State',
    'wright state raiders': 'Wright State',
    'idaho st bengals': 'Idaho State',
    'idaho state bengals': 'Idaho State',
    'long beach st beach': 'Long Beach State',
    'long beach state 49ers': 'Long Beach State',
    'chicago st cougars': 'Chicago State',
    'chicago state cougars': 'Chicago State',
    'tarleton st texans': 'Tarleton State',
    'tarleton state texans': 'Tarleton State',
    'missouri st bears': 'Missouri State',
    'missouri state bears': 'Missouri State',
    'appalachian st mountaineers': 'Appalachian State',
    'appalachian state mountaineers': 'Appalachian State',
    'app state': 'Appalachian State',
}

for alias, canonical in manual.items():
    resolver[alias.lower()] = canonical

print(f"Updated: {len(resolver)} mappings")

# Verify
print("\nVerify key mappings:")
tests = [
    'michigan st spartans', 'michigan state spartans', 'Michigan State',
    'kansas st wildcats', 'kansas state wildcats', 'Kansas State',
    'loyola (chi) ramblers', 'east tennessee st buccaneers'
]
for t in tests:
    print(f"  {t} -> {resolver.get(t.lower(), 'NOT FOUND')}")

# Save
with open(resolver_path, 'w') as f:
    json.dump(resolver, f, indent=2, sort_keys=True)

print(f"\nSaved to {resolver_path}")
