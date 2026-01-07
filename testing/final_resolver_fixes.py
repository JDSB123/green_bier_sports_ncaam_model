"""Final resolver fixes based on actual training data formats."""
import json

resolver_path = '../services/prediction-service-python/training_data/team_aliases_db.json'
with open(resolver_path, 'r') as f:
    resolver = json.load(f)

print(f"Original: {len(resolver)} mappings")

# Based on actual training data analysis:
# Training uses: UALR, IPFW, UTRGV, Miss. Valley St., UT Martin, Loyola Maryland, Miami (FL)

final_fixes = {
    # Mississippi Valley State -> Miss. Valley St. (training format)
    'miss valley st delta devils': 'Miss. Valley St.',
    'miss valley state': 'Miss. Valley St.',
    'miss valley st': 'Miss. Valley St.',
    'mississippi valley state': 'Miss. Valley St.',
    'mississippi valley state delta devils': 'Miss. Valley St.',
    'mississippi valley st': 'Miss. Valley St.',
    'mvsu': 'Miss. Valley St.',
    'mvsu delta devils': 'Miss. Valley St.',
    
    # UALR (training uses UALR)
    'arkansas-little rock trojans': 'UALR',
    'arkansas-little rock': 'UALR',
    'arkansas little rock': 'UALR',
    'little rock trojans': 'UALR',
    'little rock': 'UALR',
    
    # IPFW (training uses IPFW)
    'fort wayne mastodons': 'IPFW',
    'fort wayne': 'IPFW',
    'purdue fort wayne mastodons': 'IPFW',
    'purdue fort wayne': 'IPFW',
    'pfw mastodons': 'IPFW',
    'pfw': 'IPFW',
    
    # UTRGV (training uses UTRGV)
    'ut rio grande valley vaqueros': 'UTRGV',
    'ut rio grande valley': 'UTRGV',
    'texas-rio grande valley': 'UTRGV',
    
    # UT Martin (training uses UT Martin)
    'tenn-martin skyhawks': 'UT Martin',
    'tenn-martin': 'UT Martin',
    'tennessee-martin': 'UT Martin',
    'tennessee martin': 'UT Martin',
    'ut martin skyhawks': 'UT Martin',
    'tennessee-martin skyhawks': 'UT Martin',
    
    # Loyola Maryland (training uses Loyola Maryland)
    'loyola (md) greyhounds': 'Loyola Maryland',
    'loyola (md)': 'Loyola Maryland',
    'loyola md': 'Loyola Maryland',
    'loyola maryland greyhounds': 'Loyola Maryland',
    'loyola-maryland': 'Loyola Maryland',
    
    # Miami FL (training uses Miami (FL))
    'miami hurricanes': 'Miami (FL)',
    'miami fl': 'Miami (FL)',
    
    # Also need to handle games_all format that uses mascot names
    'mississippi valley state delta devils': 'Miss. Valley St.',
    'ut rio grande valley vaqueros': 'UTRGV',
    'utah valley wolverines': 'Utah Valley State',
}

for alias, canonical in final_fixes.items():
    resolver[alias.lower()] = canonical

print(f"Updated: {len(resolver)} mappings")

# Save
with open(resolver_path, 'w') as f:
    json.dump(resolver, f, indent=2, sort_keys=True)

print("Saved!")

# Verify
print("\nVerify mappings:")
tests = ['miss valley st delta devils', 'mississippi valley state delta devils', 
         'arkansas-little rock trojans', 'fort wayne mastodons', 'ut rio grande valley vaqueros',
         'tenn-martin skyhawks', 'loyola (md) greyhounds', 'miami hurricanes']
for t in tests:
    print(f"  {t} -> {resolver.get(t.lower(), 'NOT FOUND')}")
