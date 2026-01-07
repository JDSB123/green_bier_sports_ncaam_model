"""Fix conflicting resolver mappings where aliases map to different canonicals."""
import json

RESOLVER_PATH = '../services/prediction-service-python/training_data/team_aliases_db.json'

with open(RESOLVER_PATH, 'r') as f:
    resolver = json.load(f)

# These are the CANONICAL forms we want to use (matching training data)
# All variations should map to these
canonical_fixes = {
    # UALR is the canonical - all variations map here
    'ualr': 'UALR',
    'little rock': 'UALR',
    'little rock trojans': 'UALR',
    'arkansas-little rock': 'UALR',
    'arkansas-little rock trojans': 'UALR',
    'arkansas little rock': 'UALR',
    'ar-little rock': 'UALR',
    
    # UTRGV is the canonical
    'utrgv': 'UTRGV',
    'ut rio grande valley': 'UTRGV',
    'ut rio grande valley vaqueros': 'UTRGV',
    'texas-rio grande valley': 'UTRGV',
    'texas rio grande valley': 'UTRGV',
    'rio grande valley': 'UTRGV',
    
    # IPFW is the canonical
    'ipfw': 'IPFW',
    'fort wayne': 'IPFW',
    'fort wayne mastodons': 'IPFW',
    'purdue fort wayne': 'IPFW',
    'purdue fort wayne mastodons': 'IPFW',
    'pfw mastodons': 'IPFW',
    'purdue-fort wayne': 'IPFW',
    
    # Miss. Valley St. is the canonical (training data uses this)
    'miss. valley st.': 'Miss. Valley St.',
    'miss valley st': 'Miss. Valley St.',
    'mississippi valley st': 'Miss. Valley St.',
    'mississippi valley state': 'Miss. Valley St.',
    'mississippi valley st.': 'Miss. Valley St.',
    'mississippi valley state delta devils': 'Miss. Valley St.',
    'miss valley st delta devils': 'Miss. Valley St.',
    'mvsu': 'Miss. Valley St.',
    'mvsu delta devils': 'Miss. Valley St.',
    
    # UT Martin is the canonical
    'ut martin': 'UT Martin',
    'tenn-martin': 'UT Martin',
    'tennessee-martin': 'UT Martin',
    'tennessee martin': 'UT Martin',
    'ut martin skyhawks': 'UT Martin',
    'tenn-martin skyhawks': 'UT Martin',
    'tennessee-martin skyhawks': 'UT Martin',
    
    # Loyola Maryland is the canonical
    'loyola maryland': 'Loyola Maryland',
    'loyola (md)': 'Loyola Maryland',
    'loyola md': 'Loyola Maryland',
    'loyola-maryland': 'Loyola Maryland',
    'loyola maryland greyhounds': 'Loyola Maryland',
    'loyola (md) greyhounds': 'Loyola Maryland',
    
    # Miami (FL) is the canonical
    'miami (fl)': 'Miami (FL)',
    'miami fl': 'Miami (FL)',
    'miami hurricanes': 'Miami (FL)',
    'miami': 'Miami (FL)',
    
    # Miami (Ohio) is the canonical
    'miami (ohio)': 'Miami (Ohio)',
    'miami oh': 'Miami (Ohio)',
    'miami ohio': 'Miami (Ohio)',
    'miami (oh)': 'Miami (Ohio)',
    'miami redhawks': 'Miami (Ohio)',
    'miami (oh) redhawks': 'Miami (Ohio)',
    
    # Middle Tenn. St. variations
    'middle tenn. st.': 'Middle Tenn. St.',
    'middle tenn st': 'Middle Tenn. St.',
    'mtsu': 'Middle Tenn. St.',
    'middle tennessee': 'Middle Tenn. St.',
    'middle tennessee state': 'Middle Tenn. St.',
    'middle tennessee blue raiders': 'Middle Tenn. St.',
    'middle tennessee state blue raiders': 'Middle Tenn. St.',
    
    # Sam Houston St. variations
    'sam houston st.': 'Sam Houston St.',
    'sam houston': 'Sam Houston St.',
    'sam houston state': 'Sam Houston St.',
    'sam houston bearkats': 'Sam Houston St.',
    'shsu': 'Sam Houston St.',
    'shsu bearkats': 'Sam Houston St.',
    
    # Illinois (Chi.) / UIC
    'illinois (chi.)': 'Illinois (Chi.)',
    'illinois chicago': 'Illinois (Chi.)',
    'illinois-chicago': 'Illinois (Chi.)',
    'uic': 'Illinois (Chi.)',
    'uic flames': 'Illinois (Chi.)',
    'illinois chicago flames': 'Illinois (Chi.)',
    'illinois-chicago flames': 'Illinois (Chi.)',
    
    # North Dakota St
    'north dakota st': 'North Dakota St',
    'north dakota state': 'North Dakota St',
    'ndsu': 'North Dakota St',
    'north dakota state bison': 'North Dakota St',
    'ndsu bison': 'North Dakota St',
}

print(f"Original: {len(resolver)} mappings")

# Apply fixes (overwrite any conflicting entries)
for alias, canonical in canonical_fixes.items():
    resolver[alias.lower().strip()] = canonical

print(f"After fixes: {len(resolver)} mappings")

# Save
with open(RESOLVER_PATH, 'w') as f:
    json.dump(resolver, f, indent=2)

# Verify key mappings
print("\nVerify critical mappings:")
test_cases = [
    ('ualr', 'UALR'),
    ('little rock trojans', 'UALR'),
    ('utrgv', 'UTRGV'),
    ('ut rio grande valley', 'UTRGV'),
    ('ipfw', 'IPFW'),
    ('purdue fort wayne mastodons', 'IPFW'),
    ('miss. valley st.', 'Miss. Valley St.'),
    ('mississippi valley state delta devils', 'Miss. Valley St.'),
]
all_ok = True
for alias, expected in test_cases:
    actual = resolver.get(alias, 'NOT FOUND')
    status = '✅' if actual == expected else '❌'
    if actual != expected:
        all_ok = False
    print(f"  {status} {alias} -> {actual} (expected: {expected})")

if all_ok:
    print("\n✅ All critical mappings are correct!")
else:
    print("\n❌ Some mappings are incorrect!")
