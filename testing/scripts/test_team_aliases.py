#!/usr/bin/env python3
"""Quick test to verify team alias fixes."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from testing.production_parity.team_resolver import ProductionTeamResolver

r = ProductionTeamResolver()

tests = [
    ('Mississippi', 'Ole Miss'),
    ('N.C. State', 'NC State'),
    ('Tennessee Martin', 'UT Martin'),
    ('UTRGV', 'UT Rio Grande Valley'),
    ('UT Rio Grande Valley', 'UT Rio Grande Valley'),
    ('IU Indy', 'IU Indy'),
    ('IUPUI', 'IU Indy'),
    ('IU Indianapolis Jaguars', 'IU Indy'),
    ('Charleston So.', 'Charleston Southern'),
    ('Charleston Southern', 'Charleston Southern'),
    ('FAU', 'Florida Atlantic'),
    ('Florida Atlantic', 'Florida Atlantic'),
    ('Texas A&M Corpus Chris', 'Texas A&M Corpus Christi'),
    ('Texas A&M Corpus Christi', 'Texas A&M Corpus Christi'),
]

all_pass = True
for name, expected in tests:
    result = r.resolve(name)
    status = 'OK' if result.canonical_name == expected else 'FAIL'
    if status == 'FAIL':
        all_pass = False
    print(f'{name:35} -> {str(result.canonical_name):35} (expected {expected}) [{status}]')

print()
if all_pass:
    print("✅ All team alias resolutions PASSED")
else:
    print("❌ Some team alias resolutions FAILED")
