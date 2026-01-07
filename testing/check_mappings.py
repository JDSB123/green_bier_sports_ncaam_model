import json
with open('../services/prediction-service-python/training_data/team_aliases_db.json', 'r') as f:
    r = json.load(f)

tests = ['niagara', 'niagara purple', 'niagara purple eagles', 'wagner', 'wagner seahawks', 'stonehill', 'stonehill skyhawks']
for t in tests:
    result = r.get(t.lower(), 'NOT FOUND')
    print(f"{t} -> {result}")
