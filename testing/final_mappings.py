"""Add final batch of team name mappings based on mismatches found."""
import json

resolver_path = '../services/prediction-service-python/training_data/team_aliases_db.json'
with open(resolver_path, 'r') as f:
    resolver = json.load(f)

print(f"Original: {len(resolver)} mappings")

# All the mismatches found - map odds format to training format
final_mappings = {
    # State name variations
    'minnesota golden gophers': 'Minnesota',
    'minnesota golden': 'Minnesota',
    
    # Louisiana variations
    'louisiana ragin\' cajuns': 'Louisiana Lafayette',
    'louisiana': 'Louisiana Lafayette',
    'louisiana ragin cajuns': 'Louisiana Lafayette',
    'ul lafayette': 'Louisiana Lafayette',
    'louisiana-lafayette': 'Louisiana Lafayette',
    
    # Miami variations
    'miami (oh) redhawks': 'Miami (Ohio)',
    'miami (oh)': 'Miami (Ohio)',
    'miami oh': 'Miami (Ohio)',
    'miami hurricanes': 'Miami (FL)',
    'miami fl': 'Miami (FL)',
    
    # Saint/St variations
    'saint joseph\'s hawks': 'Saint Josephs Hawks',
    'saint joseph\'s': 'Saint Josephs Hawks',
    'st. joseph\'s hawks': 'Saint Josephs Hawks',
    'st. joseph\'s': 'Saint Josephs Hawks',
    'saint josephs': 'Saint Josephs Hawks',
    
    'saint mary\'s gaels': 'St. Marys (CA)',
    'saint mary\'s': 'St. Marys (CA)',
    'st. mary\'s gaels': 'St. Marys (CA)',
    'st. mary\'s': 'St. Marys (CA)',
    'st. marys': 'St. Marys (CA)',
    
    'st. john\'s red storm': 'St. John\'s (N.Y.)',
    'st. john\'s': 'St. John\'s (N.Y.)',
    'saint john\'s red storm': 'St. John\'s (N.Y.)',
    'saint john\'s': 'St. John\'s (N.Y.)',
    
    'saint peter\'s peacocks': 'St. Peters',
    'saint peter\'s': 'St. Peters',
    'st. peter\'s peacocks': 'St. Peters',
    'st. peter\'s': 'St. Peters',
    
    'saint louis billikens': 'St. Louis Billikens',
    'saint louis': 'St. Louis Billikens',
    'st. louis': 'St. Louis Billikens',
    
    'st. thomas (mn) tommies': 'St. Thomas (Minn.)',
    'st. thomas (mn)': 'St. Thomas (Minn.)',
    'st. thomas minnesota': 'St. Thomas (Minn.)',
    
    'st. francis (pa) red flash': 'St. Francis (PA)',
    'st. francis pa': 'St. Francis (PA)',
    
    'mt. st. mary\'s mountaineers': 'Mount St. Mary\'s',
    'mt. st. mary\'s': 'Mount St. Mary\'s',
    'mount st. mary\'s mountaineers': 'Mount St. Mary\'s',
    'mount st marys': 'Mount St. Mary\'s',
    
    # Hawaii
    'hawai\'i rainbow warriors': 'Hawaii',
    'hawai\'i': 'Hawaii',
    'hawaii rainbow warriors': 'Hawaii',
    
    # UIC
    'uic flames': 'Illinois (Chi.)',
    'uic': 'Illinois (Chi.)',
    'illinois-chicago': 'Illinois (Chi.)',
    
    # Bryant
    'bryant bulldogs': 'Bryant University',
    'bryant': 'Bryant University',
    
    # Arkansas Little Rock
    'arkansas-little rock trojans': 'UALR',
    'arkansas-little rock': 'UALR',
    'arkansas little rock': 'UALR',
    
    # San Jose State (accent)
    'san josé st spartans': 'San Jose State',
    'san josé state': 'San Jose State',
    'san jose st spartans': 'San Jose State',
    
    # East Tennessee State
    'east tennessee st buccaneers': 'East Tennessee St',
    'east tennessee state': 'East Tennessee St',
    'east tennessee state buccaneers': 'East Tennessee St',
    'etsu': 'East Tennessee St',
    
    # UNC Wilmington
    'unc wilmington seahawks': 'NC Wilmington',
    'unc wilmington': 'NC Wilmington',
    'unc-wilmington': 'NC Wilmington',
    
    # Florida International
    'florida int\'l golden panthers': 'Florida International',
    'florida int\'l golden': 'Florida International',
    'florida int\'l': 'Florida International',
    'fiu golden panthers': 'Florida International',
    'fiu': 'Florida International',
    
    # Cal Baptist
    'cal baptist lancers': 'California Baptist',
    'cal baptist': 'California Baptist',
    
    # Lipscomb
    'lipscomb bisons': 'Lipscomb',
    
    # CSU schools
    'csu fullerton titans': 'CS Fullerton',
    'csu fullerton': 'CS Fullerton',
    'cal state fullerton': 'CS Fullerton',
    
    'csu northridge matadors': 'CS Northridge',
    'csu northridge': 'CS Northridge',
    'cal state northridge': 'CS Northridge',
    
    # Northern Colorado
    'n colorado bears': 'Northern Colorado',
    'n colorado': 'Northern Colorado',
    'n. colorado': 'Northern Colorado',
    
    # Middle Tennessee
    'middle tennessee blue raiders': 'Middle Tenn. St.',
    'middle tennessee blue': 'Middle Tenn. St.',
    'middle tennessee': 'Middle Tenn. St.',
    'middle tennessee state': 'Middle Tenn. St.',
    'mtsu': 'Middle Tenn. St.',
    
    # Drexel
    'drexel dragons': 'Drexel',
    
    # Sam Houston
    'sam houston st bearkats': 'Sam Houston St.',
    'sam houston state': 'Sam Houston St.',
    'sam houston state bearkats': 'Sam Houston St.',
    'sam houston': 'Sam Houston St.',
    
    # Omaha
    'omaha mavericks': 'Nebraska O.',
    'omaha': 'Nebraska O.',
    'nebraska-omaha': 'Nebraska O.',
    
    # Grand Canyon
    'grand canyon antelopes': 'Grand Canyon',
    
    # SE Missouri
    'se missouri st redhawks': 'Southeast Missouri State',
    'se missouri state': 'Southeast Missouri State',
    'se missouri st': 'Southeast Missouri State',
    'semo redhawks': 'Southeast Missouri State',
    
    # Binghamton
    'binghamton bearcats': 'Binghamton',
    
    # Mississippi Valley State
    'miss valley st delta devils': 'Miss. Valley St.',
    'miss valley state': 'Miss. Valley St.',
    'miss valley st': 'Miss. Valley St.',
    'mississippi valley state': 'Miss. Valley St.',
    'mississippi valley state delta devils': 'Miss. Valley St.',
    'mvsu': 'Miss. Valley St.',
    
    # Eastern Washington
    'eastern washington eagles': 'East. Washington',
    'eastern washington': 'East. Washington',
    'ewu': 'East. Washington',
    
    # Prairie View
    'prairie view panthers': 'Prairie View A&M',
    'prairie view': 'Prairie View A&M',
    'prairie view a&m panthers': 'Prairie View A&M',
    
    # Maryland Eastern Shore
    'maryland-eastern shore hawks': 'Md.-East. Shore',
    'maryland-eastern shore': 'Md.-East. Shore',
    'umes': 'Md.-East. Shore',
    
    # North Carolina A&T
    'north carolina a&t aggies': 'N. Carolina A&T',
    'north carolina a&t': 'N. Carolina A&T',
    'nc a&t': 'N. Carolina A&T',
    
    # Bellarmine
    'bellarmine knights': 'Bellarmine',
    
    # Gardner-Webb
    'gardner-webb bulldogs': 'Gardner Webb',
    'gardner-webb': 'Gardner Webb',
    
    # Arkansas Pine Bluff
    'arkansas-pine bluff golden lions': 'Arkansas-Pine Bluff',
    'arkansas-pine bluff golden': 'Arkansas-Pine Bluff',
    'uapb': 'Arkansas-Pine Bluff',
    
    # VMI
    'vmi keydets': 'VMI',
    
    # William & Mary
    'william & mary tribe': 'William & Mary',
    
    # North Carolina Central
    'north carolina central eagles': 'N. Carolina Central',
    'north carolina central': 'N. Carolina Central',
    'nccu': 'N. Carolina Central',
    
    # Queens
    'queens university royals': 'Queens Royals',
    'queens university': 'Queens Royals',
    
    # Niagara
    'niagara purple eagles': 'Niagara',
    'niagara purple': 'Niagara',
    
    # USC Upstate
    'south carolina upstate spartans': 'USC Upstate',
    'south carolina upstate': 'USC Upstate',
    'sc upstate': 'USC Upstate',
    
    # Boston University
    'boston univ. terriers': 'Boston University',
    'boston univ.': 'Boston University',
    'bu terriers': 'Boston University',
    
    # Loyola Maryland
    'loyola (md) greyhounds': 'Loyola Maryland',
    'loyola (md)': 'Loyola Maryland',
    'loyola md': 'Loyola Maryland',
    
    # Presbyterian
    'presbyterian blue hose': 'Presbyterian',
    
    # American
    'american eagles': 'American',
    'american university': 'American',
    
    # Fort Wayne
    'fort wayne mastodons': 'Fort Wayne',
    'purdue fort wayne': 'Fort Wayne',
    'purdue fort wayne mastodons': 'Fort Wayne',
    'pfw': 'Fort Wayne',
    
    # GW
    'gw revolutionaries': 'George Washington',
    'george washington revolutionaries': 'George Washington',
    'george washington colonials': 'George Washington',
    
    # Houston Baptist
    'houston baptist': 'Houston Christian',
    'houston baptist huskies': 'Houston Christian',
    'houston christian huskies': 'Houston Christian',
    
    # LIU
    'liu brooklyn blackbirds': 'Long Island',
    'liu brooklyn': 'Long Island',
    'liu sharks': 'Long Island',
    'liu': 'Long Island',
    'long island university': 'Long Island',
    
    # Northwestern State
    'northwestern st demons': 'Northwestern State',
    'northwestern state demons': 'Northwestern State',
    
    # Tennessee Martin
    'tenn-martin': 'Tennessee-Martin',
    'ut martin': 'Tennessee-Martin',
    'ut martin skyhawks': 'Tennessee-Martin',
    'tennessee-martin skyhawks': 'Tennessee-Martin',
    
    # Texas A&M CC
    'texas a&m-cc islanders': 'Texas A&M Corpus Chris',
    'texas a&m-corpus christi': 'Texas A&M Corpus Chris',
    'texas a&m corpus christi': 'Texas A&M Corpus Chris',
    'tamucc': 'Texas A&M Corpus Chris',
    
    # Texas A&M Commerce
    'texas a&m-commerce': 'Texas A&M Commerce',
    'texas a&m commerce lions': 'Texas A&M Commerce',
    
    # Valparaiso
    'valparaiso crusaders': 'Valparaiso',
    'valparaiso beacons': 'Valparaiso',
    
    # McNeese
    'mcneese st mcneese': 'McNeese',
    'mcneese st cowboys': 'McNeese',
    'mcneese state': 'McNeese',
    'mcneese state cowboys': 'McNeese',
    
    # Wagner
    'wagner seahawks': 'Wagner',
    
    # Stonehill
    'stonehill skyhawks': 'Stonehill',
    
    # St Francis Brooklyn
    'st. francis bkn': 'St. Francis Brooklyn',
    'st. francis (bkn)': 'St. Francis Brooklyn',
    'st. francis brooklyn terriers': 'St. Francis Brooklyn',
    
    # Siena
    'siena saints': 'Siena',
}

for alias, canonical in final_mappings.items():
    resolver[alias.lower()] = canonical

print(f"Updated: {len(resolver)} mappings")

# Save
with open(resolver_path, 'w') as f:
    json.dump(resolver, f, indent=2, sort_keys=True)

print(f"Saved to {resolver_path}")

# Verify some key mappings
print("\nVerify:")
tests = ['minnesota golden gophers', 'miami (oh) redhawks', 'saint mary\'s gaels', 
         'louisiana ragin\' cajuns', 'niagara purple', 'wagner seahawks']
for t in tests:
    print(f"  {t} -> {resolver.get(t.lower(), 'NOT FOUND')}")
