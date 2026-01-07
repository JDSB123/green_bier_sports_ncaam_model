"""Add more mappings based on latest mismatches."""
import json

resolver_path = '../services/prediction-service-python/training_data/team_aliases_db.json'
with open(resolver_path, 'r') as f:
    resolver = json.load(f)

print(f"Original: {len(resolver)} mappings")

more_mappings = {
    # These are normalizing TO training data format
    
    # Fairleigh Dickinson
    'fairleigh dickinson knights': 'Fairleigh Dickinson',
    'fairleigh dickinson': 'Fairleigh Dickinson',
    
    # Campbell
    'campbell fighting camels': 'Campbell',
    
    # UNC Greensboro
    'unc greensboro spartans': 'NC Greensboro',
    'unc greensboro': 'NC Greensboro',
    'unc-greensboro': 'NC Greensboro',
    'uncg': 'NC Greensboro',
    
    # Navy
    'navy midshipmen': 'Navy',
    
    # Southern Indiana
    'southern indiana screaming eagles': 'Southern Indiana',
    'southern indiana screaming': 'Southern Indiana',
    'usi': 'Southern Indiana',
    
    # Utah Valley
    'utah valley wolverines': 'Utah Valley State',
    'utah valley': 'Utah Valley State',
    'uvu': 'Utah Valley State',
    
    # Southern Utah
    'southern utah thunderbirds': 'Southern Utah',
    
    # Fort Wayne / IPFW
    'fort wayne mastodons': 'IPFW',
    'fort wayne': 'IPFW',
    'pfw mastodons': 'IPFW',
    'purdue fort wayne': 'IPFW',
    
    # North Dakota State
    'north dakota st bison': 'North Dakota St',
    'north dakota state': 'North Dakota St',
    'north dakota state bison': 'North Dakota St',
    'ndsu': 'North Dakota St',
    
    # Milwaukee
    'milwaukee panthers': 'Wisc. Milwaukee',
    'milwaukee': 'Wisc. Milwaukee',
    'wisconsin-milwaukee': 'Wisc. Milwaukee',
    'uw-milwaukee': 'Wisc. Milwaukee',
    
    # Utah Tech
    'utah tech trailblazers': 'Utah Tech',
    
    # Oakland
    'oakland golden grizzlies': 'Oakland',
    'oakland golden': 'Oakland',
    
    # Tennessee Martin / UT Martin
    'tenn-martin skyhawks': 'UT Martin',
    'tenn-martin': 'UT Martin',
    'tennessee-martin': 'UT Martin',
    'tennessee martin': 'UT Martin',
    'tennessee-martin skyhawks': 'UT Martin',
    
    # Texas A&M-CC
    'texas a&m-cc islanders': 'Texas A&M-CC',
    'texas a&m corpus chris': 'Texas A&M-CC',
    'texas a&m-corpus christi': 'Texas A&M-CC',
    'texas a&m corpus christi': 'Texas A&M-CC',
    'tamucc': 'Texas A&M-CC',
    
    # Southern
    'southern jaguars': 'Southern Univ.',
    'southern': 'Southern Univ.',
    'southern university': 'Southern Univ.',
    
    # Northwestern State
    'northwestern st demons': 'Northwestern St.',
    'northwestern state': 'Northwestern St.',
    'northwestern state demons': 'Northwestern St.',
    
    # Texas A&M Commerce
    'texas a&m-commerce lions': 'TX A&M Commerce',
    'texas a&m-commerce': 'TX A&M Commerce',
    'texas a&m commerce': 'TX A&M Commerce',
    'texas a&m commerce lions': 'TX A&M Commerce',
    
    # Green Bay
    'green bay phoenix': 'Wisc. Green Bay',
    'green bay': 'Wisc. Green Bay',
    'wisconsin-green bay': 'Wisc. Green Bay',
    'uw-green bay': 'Wisc. Green Bay',
    
    # UTRGV
    'ut rio grande valley vaqueros': 'UTRGV',
    'ut rio grande valley': 'UTRGV',
    'texas-rio grande valley': 'UTRGV',
    
    # Lehigh
    'lehigh mountain hawks': 'Lehigh',
    'lehigh mountain': 'Lehigh',
    
    # New Orleans
    'new orleans privateers': 'New Orleans',
    'uno privateers': 'New Orleans',
    
    # West Georgia
    'west georgia wolves': 'West Georgia',
    
    # IUPUI / IU Indy
    'iupui jaguars': 'IU Indy',
    'iupui': 'IU Indy',
    'indiana university-purdue university indianapolis': 'IU Indy',
    
    # Army
    'army knights': 'Army Black Knights',
    'army': 'Army Black Knights',
    'army west point': 'Army Black Knights',
    
    # CSU Fullerton - conflicting, align to training
    'csu fullerton titans': 'Cal State Fullerton Titans',
    'csu fullerton': 'Cal State Fullerton Titans',
    'cs fullerton': 'Cal State Fullerton Titans',
    'cal state fullerton': 'Cal State Fullerton Titans',
    
    # CSU Bakersfield
    'csu bakersfield roadrunners': 'Cal State Bakersfield Roadrunners',
    'csu bakersfield': 'Cal State Bakersfield Roadrunners',
    'cs bakersfield': 'Cal State Bakersfield Roadrunners',
    'cal state bakersfield': 'Cal State Bakersfield Roadrunners',
    
    # Miss Valley State - already mapped but verify
    'miss valley st delta devils': 'Miss. Valley St.',
    'miss valley state': 'Miss. Valley St.',
    'mississippi valley state': 'Miss. Valley St.',
    'mississippi valley state delta devils': 'Miss. Valley St.',
    'mvsu delta devils': 'Miss. Valley St.',
    
    # Loyola Maryland - verify correct
    'loyola (md) greyhounds': 'Loyola Maryland',
    'loyola (md)': 'Loyola Maryland',
    'loyola md': 'Loyola Maryland',
    'loyola-maryland': 'Loyola Maryland',
}

for alias, canonical in more_mappings.items():
    resolver[alias.lower()] = canonical

print(f"Updated: {len(resolver)} mappings")

# Save
with open(resolver_path, 'w') as f:
    json.dump(resolver, f, indent=2, sort_keys=True)

print("Saved!")

# Verify
print("\nVerify:")
tests = ['unc greensboro spartans', 'fort wayne mastodons', 'milwaukee panthers', 
         'tenn-martin skyhawks', 'southern jaguars']
for t in tests:
    print(f"  {t} -> {resolver.get(t.lower(), 'NOT FOUND')}")
