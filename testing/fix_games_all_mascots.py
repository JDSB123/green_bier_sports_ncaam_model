"""Fix: games_all uses mascot names that need to map to same canonical as odds."""
import json

RESOLVER_PATH = '../services/prediction-service-python/training_data/team_aliases_db.json'

with open(RESOLVER_PATH, 'r') as f:
    resolver = json.load(f)

# games_all uses mascot format that need to map to SAME canonical as odds
# Odds normalizes to: UALR, Miss. Valley St., IPFW, UT Martin, Loyola Maryland, etc.
# games_all has: Little Rock Trojans, Mississippi Valley State Delta Devils, etc.

fixes = {
    # UALR - odds has "UALR", games_all has "Little Rock Trojans"
    'little rock trojans': 'UALR',
    'arkansas-little rock trojans': 'UALR',
    'arkansas-little rock': 'UALR',
    
    # Miss. Valley St. - odds has "Miss. Valley St.", games_all has "Mississippi Valley State Delta Devils"
    'mississippi valley state delta devils': 'Miss. Valley St.',
    'mississippi valley st delta devils': 'Miss. Valley St.',
    'mississippi valley state': 'Miss. Valley St.',
    'mississippi valley st.': 'Miss. Valley St.',
    'mvsu delta devils': 'Miss. Valley St.',
    
    # IPFW - odds has "IPFW", games_all has "Purdue Fort Wayne Mastodons" / "Fort Wayne Mastodons"
    'purdue fort wayne mastodons': 'IPFW',
    'fort wayne mastodons': 'IPFW',
    'purdue fort wayne': 'IPFW',
    'fort wayne': 'IPFW',
    
    # UT Martin - odds has "UT Martin", games_all has "UT Martin Skyhawks"
    'ut martin skyhawks': 'UT Martin',
    'tennessee-martin skyhawks': 'UT Martin',
    'tenn-martin skyhawks': 'UT Martin',
    'tennessee-martin': 'UT Martin',
    'tenn-martin': 'UT Martin',
    
    # Loyola Maryland - odds has "Loyola Maryland", games_all has "Loyola Maryland Greyhounds"
    'loyola maryland greyhounds': 'Loyola Maryland',
    'loyola (md) greyhounds': 'Loyola Maryland',
    'loyola-maryland greyhounds': 'Loyola Maryland',
    'loyola (md)': 'Loyola Maryland',
    'loyola-maryland': 'Loyola Maryland',
    'loyola md': 'Loyola Maryland',
    
    # Middle Tennessee - different formats
    'middle tennessee blue raiders': 'Middle Tenn. St.',
    'middle tennessee state blue raiders': 'Middle Tenn. St.',
    'middle tenn. st.': 'Middle Tenn. St.',
    'middle tennessee': 'Middle Tenn. St.',
    'middle tennessee state': 'Middle Tenn. St.',
    'middle tenn st': 'Middle Tenn. St.',
    'mtsu blue raiders': 'Middle Tenn. St.',
    
    # Sam Houston - different formats
    'sam houston bearkats': 'Sam Houston St.',
    'sam houston state bearkats': 'Sam Houston St.',
    'sam houston st.': 'Sam Houston St.',
    'sam houston state': 'Sam Houston St.',
    'sam houston': 'Sam Houston St.',
    'shsu bearkats': 'Sam Houston St.',
    
    # Northwestern State
    'northwestern state demons': 'Northwestern St.',
    'northwestern st. demons': 'Northwestern St.',
    'northwestern st.': 'Northwestern St.',
    'northwestern state': 'Northwestern St.',
    'northwestern st': 'Northwestern St.',
    
    # Illinois-Chicago / UIC
    'uic flames': 'Illinois (Chi.)',
    'illinois chicago flames': 'Illinois (Chi.)',
    'illinois-chicago flames': 'Illinois (Chi.)',
    'illinois (chi.)': 'Illinois (Chi.)',
    'illinois chicago': 'Illinois (Chi.)',
    'illinois-chicago': 'Illinois (Chi.)',
    'uic': 'Illinois (Chi.)',
    
    # North Dakota State
    'north dakota state bison': 'North Dakota St',
    'north dakota st bison': 'North Dakota St',
    'north dakota st': 'North Dakota St',
    'north dakota state': 'North Dakota St',
    'ndsu bison': 'North Dakota St',
    
    # Utah Valley
    'utah valley wolverines': 'Utah Valley State',
    'utah valley state wolverines': 'Utah Valley State',
    'utah valley': 'Utah Valley State',
    'uvu wolverines': 'Utah Valley State',
    
    # Stephen F. Austin
    'stephen f austin lumberjacks': 'Stephen F. Austin',
    'sfa lumberjacks': 'Stephen F. Austin',
    'stephen f. austin lumberjacks': 'Stephen F. Austin',
    'sfa': 'Stephen F. Austin',
    
    # Weber State
    'weber state wildcats': 'Weber State',
    'weber st wildcats': 'Weber State',
    'weber st': 'Weber State',
    
    # Texas State
    'texas state bobcats': 'Texas State',
    'texas st bobcats': 'Texas State',
    'texas st': 'Texas State',
    
    # Kent State
    'kent state golden flashes': 'Kent State',
    'kent st golden flashes': 'Kent State',
    'kent st': 'Kent State',
    
    # James Madison
    'james madison dukes': 'James Madison',
    'jmu dukes': 'James Madison',
    'jmu': 'James Madison',
    
    # UAB
    'uab blazers': 'UAB',
    'alabama-birmingham blazers': 'UAB',
    'alabama birmingham': 'UAB',
    
    # Bradley
    'bradley braves': 'Bradley',
    
    # Fordham
    'fordham rams': 'Fordham',
    
    # Wagner
    'wagner seahawks': 'Wagner',
    
    # Western Illinois
    'western illinois leathernecks': 'Western Illinois',
    'western ill leathernecks': 'Western Illinois',
    'western ill': 'Western Illinois',
    
    # Northern Iowa
    'northern iowa panthers': 'Northern Iowa',
    'uni panthers': 'Northern Iowa',
    'uni': 'Northern Iowa',
    
    # UTSA
    'utsa roadrunners': 'UTSA',
    'texas-san antonio roadrunners': 'UTSA',
    'texas san antonio': 'UTSA',
    'texas-san antonio': 'UTSA',
    
    # Western Michigan
    'western michigan broncos': 'Western Michigan',
    'western mich broncos': 'Western Michigan',
    'western mich': 'Western Michigan',
    
    # Radford
    'radford highlanders': 'Radford',
    
    # Marshall  
    'marshall thundering herd': 'Marshall',
    
    # Jacksonville State
    'jacksonville state gamecocks': 'Jacksonville State',
    'jax state gamecocks': 'Jacksonville State',
    'jax state': 'Jacksonville State',
    
    # Utah Tech
    'utah tech trailblazers': 'Utah Tech',
    
    # Georgia
    'georgia bulldogs': 'Georgia',
    'uga bulldogs': 'Georgia',
    
    # Oregon  
    'oregon ducks': 'Oregon',
    
    # Florida
    'florida gators': 'Florida',
    
    # LSU
    'lsu tigers': 'LSU',
    'louisiana state tigers': 'LSU',
    
    # DePaul
    'depaul blue demons': 'DePaul',
}

print(f"Original: {len(resolver)} mappings")

for alias, canonical in fixes.items():
    alias_lower = alias.lower().strip()
    if alias_lower not in resolver:
        resolver[alias_lower] = canonical

print(f"Updated: {len(resolver)} mappings")

# Save
with open(RESOLVER_PATH, 'w') as f:
    json.dump(resolver, f, indent=2)

# Verify
print("\nVerify key mappings:")
test_cases = [
    'little rock trojans',
    'mississippi valley state delta devils',
    'purdue fort wayne mastodons',
    'ut martin skyhawks',
    'loyola maryland greyhounds',
    'middle tennessee blue raiders',
    'sam houston bearkats',
    'uic flames',
]
for tc in test_cases:
    print(f"  {tc} -> {resolver.get(tc, 'NOT FOUND')}")
