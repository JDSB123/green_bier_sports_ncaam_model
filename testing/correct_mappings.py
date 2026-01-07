"""Fix resolver to use the ACTUAL most common training data variant."""
import json

resolver_path = '../services/prediction-service-python/training_data/team_aliases_db.json'
with open(resolver_path, 'r') as f:
    resolver = json.load(f)

print(f"Original: {len(resolver)} mappings")

# Based on actual counts from previous run:
# fort wayne: IPFW (61 games) is most common
# loyola maryland: Loyola Maryland (59 games) is most common
# ut martin: UT Martin (58 games) is most common  
# miami fl: Miami Hurricanes (84 games) is most common
# utrgv: UTRGV (60 games) is most common
# little rock: UALR (62 games) is most common
# mississippi valley: Miss. Valley St. (61 games) is most common

correct_mappings = {
    # Fort Wayne -> IPFW (most common)
    'fort wayne mastodons': 'IPFW',
    'fort wayne': 'IPFW',
    'purdue fort wayne mastodons': 'IPFW',
    'purdue fort wayne': 'IPFW',
    'pfw mastodons': 'IPFW',
    'pfw': 'IPFW',
    
    # Loyola Maryland -> Loyola Maryland (most common)
    'loyola (md) greyhounds': 'Loyola Maryland',
    'loyola (md)': 'Loyola Maryland',
    'loyola md': 'Loyola Maryland',
    'loyola maryland greyhounds': 'Loyola Maryland',
    'loyola-maryland': 'Loyola Maryland',
    
    # UT Martin -> UT Martin (most common)
    'tenn-martin skyhawks': 'UT Martin',
    'tenn-martin': 'UT Martin',
    'tennessee-martin': 'UT Martin',
    'tennessee martin': 'UT Martin',
    'ut martin skyhawks': 'UT Martin',
    'tennessee-martin skyhawks': 'UT Martin',
    
    # Miami FL -> Miami Hurricanes (most common)
    'miami (fl)': 'Miami Hurricanes',
    'miami fl': 'Miami Hurricanes',
    
    # UTRGV -> UTRGV (already correct)
    'ut rio grande valley vaqueros': 'UTRGV',
    'ut rio grande valley': 'UTRGV',
    'texas-rio grande valley': 'UTRGV',
    
    # Little Rock -> UALR (most common)
    'arkansas-little rock trojans': 'UALR',
    'arkansas-little rock': 'UALR',
    'arkansas little rock': 'UALR',
    'little rock trojans': 'UALR',
    'little rock': 'UALR',
    
    # Mississippi Valley State -> Miss. Valley St. (most common)
    'miss valley st delta devils': 'Miss. Valley St.',
    'miss valley state': 'Miss. Valley St.',
    'miss valley st': 'Miss. Valley St.',
    'mississippi valley state': 'Miss. Valley St.',
    'mississippi valley state delta devils': 'Miss. Valley St.',
    'mvsu': 'Miss. Valley St.',
    'mvsu delta devils': 'Miss. Valley St.',
}

for alias, canonical in correct_mappings.items():
    resolver[alias.lower()] = canonical

print(f"Updated: {len(resolver)} mappings")

# Save
with open(resolver_path, 'w') as f:
    json.dump(resolver, f, indent=2, sort_keys=True)

print("Saved!")

# Verify
print("\nVerify:")
tests = ['fort wayne mastodons', 'loyola (md)', 'tenn-martin', 'miami fl', 'little rock trojans', 'miss valley st']
for t in tests:
    print(f"  {t} -> {resolver.get(t.lower(), 'NOT FOUND')}")
