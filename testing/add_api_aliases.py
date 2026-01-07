"""Add missing API team name aliases to the resolver."""
import json

# Load current aliases
with open('production_parity/team_aliases.json', 'r') as f:
    data = json.load(f)

# The unmatched teams from API format (without periods, with mascots)
# Pattern: 'XXX St YYY' -> 'XXX St.' (adding period and removing mascot)
unmatched_mappings = {
    # SWAC / MEAC / HBCUs
    'jackson st tigers': 'Jackson St.',
    'alcorn st braves': 'Alcorn St.',
    'grambling st tigers': 'Grambling St.',
    'alabama st hornets': 'Alabama St.',
    'mississippi val st delta devils': 'Mississippi Valley St.',
    'prairie view a&m panthers': 'Prairie View A&M',
    'prairie view panthers': 'Prairie View A&M',
    'southern u jaguars': 'Southern',
    'texas southern tigers': 'Texas Southern',
    'arkansas pine bluff golden lions': 'Arkansas Pine Bluff',
    'bethune cookman wildcats': 'Bethune-Cookman',
    'coppin st eagles': 'Coppin St.',
    'delaware st hornets': 'Delaware St.',
    'howard bison': 'Howard',
    'maryland eastern shore hawks': 'Maryland Eastern Shore',
    'morgan st bears': 'Morgan St.',
    'norfolk st spartans': 'Norfolk St.',
    'nc central eagles': 'North Carolina Central',
    'south carolina st bulldogs': 'South Carolina St.',
    
    # Ohio Valley / Horizon
    'morehead st eagles': 'Morehead St.',
    'murray st racers': 'Murray St.',
    'eastern kentucky colonels': 'Eastern Kentucky',
    'tennessee st tigers': 'Tennessee St.',
    'tennessee tech golden eagles': 'Tennessee Tech',
    'austin peay governors': 'Austin Peay',
    'southeast missouri st redhawks': 'Southeast Missouri St.',
    'se missouri st redhawks': 'Southeast Missouri St.',
    'eastern illinois panthers': 'Eastern Illinois',
    'siu edwardsville cougars': 'SIU Edwardsville',
    'siu-edwardsville cougars': 'SIU Edwardsville',
    'northern kentucky norse': 'Northern Kentucky',
    'wright st raiders': 'Wright St.',
    'youngstown st penguins': 'Youngstown St.',
    'cleveland st vikings': 'Cleveland St.',
    'detroit mercy titans': 'Detroit Mercy',
    'oakland golden grizzlies': 'Oakland',
    'robert morris colonials': 'Robert Morris',
    'iupui jaguars': 'IUPUI',
    
    # Horizon / Milwaukee
    'wisconsin milwaukee panthers': 'Milwaukee',
    'wisconsin green bay phoenix': 'Green Bay',
    'green bay phoenix': 'Green Bay',
    
    # Missouri Valley
    'illinois st redbirds': 'Illinois St.',
    'indiana st sycamores': 'Indiana St.',
    'missouri st bears': 'Missouri St.',
    'southern illinois salukis': 'Southern Illinois',
    
    # Southland
    'nicholls st colonels': 'Nicholls St.',
    'sam houston st bearkats': 'Sam Houston St.',
    'mcneese st cowboys': 'McNeese St.',
    'southeastern louisiana lions': 'SE Louisiana',
    'northwestern st demons': 'Northwestern St.',
    
    # Big West / UC Schools
    'uc davis aggies': 'UC Davis',
    'cal poly mustangs': 'Cal Poly',
    'uc irvine anteaters': 'UC Irvine',
    'uc riverside highlanders': 'UC Riverside',
    'uc san diego tritons': 'UC San Diego',
    'uc santa barbara gauchos': 'UC Santa Barbara',
    'long beach st beach': 'Long Beach St.',
    'long beach st 49ers': 'Long Beach St.',
    'cal st fullerton titans': 'Cal St. Fullerton',
    'csu fullerton titans': 'Cal St. Fullerton',
    'cal st northridge matadors': 'Cal St. Northridge',
    'csu northridge matadors': 'Cal St. Northridge',
    'csu bakersfield roadrunners': 'Cal St. Bakersfield',
    'sacramento st hornets': 'Sacramento St.',
    
    # Mountain West / WAC
    'san jose st spartans': 'San Jose St.',
    'fresno st bulldogs': 'Fresno St.',
    'boise st broncos': 'Boise St.',
    'colorado st rams': 'Colorado St.',
    'utah st aggies': 'Utah St.',
    'san diego st aztecs': 'San Diego St.',
    'new mexico st aggies': 'New Mexico St.',
    
    # Sun Belt
    'texas st bobcats': 'Texas St.',
    'appalachian st mountaineers': 'Appalachian St.',
    'georgia st panthers': 'Georgia St.',
    'arkansas st red wolves': 'Arkansas St.',
    'louisiana ragin cajuns': 'Louisiana',
    'south alabama jaguars': 'South Alabama',
    
    # CUSA
    'texas arlington mavericks': 'UT Arlington',
    'ut arlington mavericks': 'UT Arlington',
    'ut-arlington mavericks': 'UT Arlington',
    'ut rio grande valley vaqueros': 'UTRGV',
    'little rock trojans': 'Little Rock',
    'western kentucky hilltoppers': 'Western Kentucky',
    'middle tennessee blue raiders': 'Middle Tennessee',
    'old dominion monarchs': 'Old Dominion',
    'marshall thundering herd': 'Marshall',
    'florida intl panthers': 'FIU',
    "florida int'l golden panthers": 'FIU',
    'fiu panthers': 'FIU',
    'texas a&m-cc islanders': 'Texas A&M Corpus Christi',
    'texas a&m corpus christi islanders': 'Texas A&M Corpus Christi',
    
    # Southern / Atlantic Sun
    'east tennessee st buccaneers': 'East Tennessee St.',
    'jacksonville st gamecocks': 'Jacksonville St.',
    'tenn-martin skyhawks': 'UT Martin',
    'ut martin skyhawks': 'UT Martin',
    
    # A10 / Atlantic 10
    'st bonaventure bonnies': "St. Bonaventure",
    'st. francis (pa) red flash': 'St. Francis PA',
    'st francis (pa) red flash': 'St. Francis PA',
    'loyola (md) greyhounds': 'Loyola MD',
    'loyola (chi) ramblers': 'Loyola Chicago',
    'boston univ. terriers': 'Boston University',
    'boston univ terriers': 'Boston University',
    
    # MAC
    'kent st golden flashes': 'Kent St.',
    'bowling green falcons': 'Bowling Green',
    'ball st cardinals': 'Ball St.',
    'ohio bobcats': 'Ohio',
    'miami (oh) redhawks': 'Miami OH',
    'miami oh redhawks': 'Miami OH',
    
    # Big Sky
    'portland st vikings': 'Portland St.',
    'northern colorado bears': 'Northern Colorado',
    'n colorado bears': 'Northern Colorado',
    'weber st wildcats': 'Weber St.',
    'idaho st bengals': 'Idaho St.',
    'montana st bobcats': 'Montana St.',
    'eastern washington eagles': 'Eastern Washington',
    'sacramento st hornets': 'Sacramento St.',
    
    # Summit
    'south dakota st jackrabbits': 'South Dakota St.',
    'north dakota st bison': 'North Dakota St.',
    'oral roberts golden eagles': 'Oral Roberts',
    'south dakota coyotes': 'South Dakota',
    'north dakota fighting hawks': 'North Dakota',
    'fort wayne mastodons': 'Purdue Fort Wayne',
    
    # NEC / Northeast
    "mount st mary's mountaineers": "Mount St. Mary's",
    "mt. st. mary's mountaineers": "Mount St. Mary's",
    "mt st mary's mountaineers": "Mount St. Mary's",
    'sacred heart pioneers': 'Sacred Heart',
    'central connecticut blue devils': 'Central Connecticut',
    'central connecticut st blue devils': 'Central Connecticut',
    'fairleigh dickinson knights': 'Fairleigh Dickinson',
    'long island sharks': 'LIU',
    'liu sharks': 'LIU',
    
    # Chicago State / WAC outliers
    'chicago st cougars': 'Chicago St.',
    
    # USC Upstate
    'south carolina upstate spartans': 'USC Upstate',
    'usc upstate spartans': 'USC Upstate',
    
    # Big Ten / P5 variations without periods
    'michigan st spartans': 'Michigan St.',
    'penn st nittany lions': 'Penn St.',
    'ohio st buckeyes': 'Ohio St.',
    'oregon st beavers': 'Oregon St.',
    'oklahoma st cowboys': 'Oklahoma St.',
    'iowa st cyclones': 'Iowa St.',
    'kansas st wildcats': 'Kansas St.',
    'washington st cougars': 'Washington St.',
    'arizona st sun devils': 'Arizona St.',
    'mississippi st bulldogs': 'Mississippi St.',
    'florida st seminoles': 'Florida St.',
    'nc st wolfpack': 'NC State',
    
    # Common alternatives with 'State' spelled out
    'jackson state tigers': 'Jackson St.',
    'morehead state eagles': 'Morehead St.',
    'cleveland state vikings': 'Cleveland St.',
    'north dakota state bison': 'North Dakota St.',
    'south dakota state jackrabbits': 'South Dakota St.',
    
    # Houston Baptist -> now Houston Christian
    'houston baptist huskies': 'Houston Christian',
    'houston christian huskies': 'Houston Christian',
    
    # Additional missing from latest run
    'detroit mercy titans': 'Detroit Mercy',
    'kennesaw st owls': 'Kennesaw St.',
    'st. thomas (mn) tommies': 'St. Thomas MN',
    'st thomas (mn) tommies': 'St. Thomas MN',
    'wichita st shockers': 'Wichita St.',
    'maryland-eastern shore hawks': 'Maryland Eastern Shore',
    'arkansas-little rock trojans': 'Little Rock',
    'ut rio grande valley vaqueros': 'UTRGV',
    'texas a&m-commerce lions': 'Texas A&M Commerce',
    'iupui jaguars': 'IUPUI',
    'tulane green wave': 'Tulane',
    'valparaiso crusaders': 'Valparaiso',
    'mcneese st mcneese': 'McNeese St.',
    'mercyhurst lakers': 'Mercyhurst',
    'west georgia wolves': 'West Georgia',
    'liu brooklyn blackbirds': 'LIU',
    'st. francis bkn terriers': 'St. Francis NY',
    'st francis bkn terriers': 'St. Francis NY',
    'new haven chargers': 'New Haven',  # D2 - will skip
    
    # Troy
    'troy trojans': 'Troy',
}

# Add to aliases (lowercase for matching)
added = 0
skipped = 0
for alias, canonical in unmatched_mappings.items():
    key = alias.lower()
    if key not in data['aliases']:
        data['aliases'][key] = canonical
        added += 1
    else:
        skipped += 1

print(f'Added {added} new aliases (skipped {skipped} existing)')
print(f'Total aliases: {len(data["aliases"])}')

# Update metadata
data['alias_count'] = len(data['aliases'])
data['version'] = '2026.01.06.1'

# Sort aliases by key
data['aliases'] = dict(sorted(data['aliases'].items()))

# Save
with open('production_parity/team_aliases.json', 'w') as f:
    json.dump(data, f, indent=2)

print('Saved updated aliases')
