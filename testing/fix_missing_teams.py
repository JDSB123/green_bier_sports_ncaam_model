"""Add missing teams to canonical names."""
import json

with open('production_parity/team_aliases.json', 'r') as f:
    data = json.load(f)

missing = ['St. Thomas MN', 'UT Martin', 'UTRGV']
added = []
for team in missing:
    if team not in data['canonical_names']:
        data['canonical_names'].append(team)
        added.append(team)

data['canonical_names'] = sorted(set(data['canonical_names']))

with open('production_parity/team_aliases.json', 'w') as f:
    json.dump(data, f, indent=2)

print(f"Added {len(added)} teams: {added}")
print(f"Total canonical names: {len(data['canonical_names'])}")
