"""Normalize all state school aliases to consistent format."""
import json

resolver_path = '../services/prediction-service-python/training_data/team_aliases_db.json'
with open(resolver_path, 'r') as f:
    resolver = json.load(f)

print(f"Original: {len(resolver)} mappings")

# All state school variations should map to "STATE" full format
# Based on what training data uses: "Michigan State", "Iowa State", etc.
state_schools = {
    # Big Ten
    'michigan state': ['michigan st.', 'michigan state', 'msu', 'michigan state spartans'],
    'ohio state': ['ohio st.', 'ohio state', 'osu', 'ohio state buckeyes'],
    'penn state': ['penn st.', 'penn state', 'psu', 'penn state nittany lions'],
    'iowa state': ['iowa st.', 'iowa state', 'isu', 'iowa state cyclones'],
    
    # Big 12
    'kansas state': ['kansas st.', 'kansas state', 'ksu', 'kansas state wildcats', 'k-state'],
    'oklahoma state': ['oklahoma st.', 'oklahoma state', 'okst', 'oklahoma state cowboys', 'osu cowboys'],
    
    # Mountain West
    'colorado state': ['colorado st.', 'colorado state', 'csu', 'colorado state rams'],
    'san diego state': ['san diego st.', 'san diego state', 'sdsu', 'san diego state aztecs'],
    'boise state': ['boise st.', 'boise state', 'bsu', 'boise state broncos'],
    'fresno state': ['fresno st.', 'fresno state', 'fresno state bulldogs'],
    'utah state': ['utah st.', 'utah state', 'utah state aggies'],
    'san jose state': ['san jose st.', 'san jose state', 'sjsu', 'san jose state spartans'],
    
    # MAC
    'kent state': ['kent st.', 'kent state', 'kent state golden flashes'],
    'ball state': ['ball st.', 'ball state', 'ball state cardinals'],
    
    # MVC
    'missouri state': ['missouri st.', 'missouri state', 'msu bears', 'missouri state bears'],
    'wichita state': ['wichita st.', 'wichita state', 'wichita state shockers'],
    'indiana state': ['indiana st.', 'indiana state', 'indiana state sycamores'],
    'illinois state': ['illinois st.', 'illinois state', 'isu redbirds', 'illinois state redbirds'],
    
    # OVC/SOCON
    'murray state': ['murray st.', 'murray state', 'murray state racers'],
    'morehead state': ['morehead st.', 'morehead state', 'morehead state eagles'],
    'tennessee state': ['tennessee st.', 'tennessee state', 'tennessee state tigers'],
    'jacksonville state': ['jacksonville st.', 'jacksonville state'],
    'appalachian state': ['appalachian st.', 'appalachian state', 'app state', 'appalachian state mountaineers'],
    
    # Sun Belt
    'arkansas state': ['arkansas st.', 'arkansas state', 'arkansas state red wolves'],
    'georgia state': ['georgia st.', 'georgia state', 'georgia state panthers'],
    'texas state': ['texas st.', 'texas state', 'texas state bobcats'],
    
    # WAC
    'tarleton state': ['tarleton st.', 'tarleton', 'tarleton state', 'tarleton state texans'],
    
    # Southland
    'mcneese state': ['mcneese st.', 'mcneese state', 'mcneese cowboys'],
    'nicholls state': ['nicholls st.', 'nicholls state', 'nicholls colonels'],
    
    # SWAC
    'jackson state': ['jackson st.', 'jackson state', 'jackson state tigers'],
    'alabama state': ['alabama st.', 'alabama state', 'alabama state hornets'],
    'grambling state': ['grambling st.', 'grambling state', 'grambling', 'grambling tigers'],
    
    # Horizon
    'cleveland state': ['cleveland st.', 'cleveland state', 'cleveland state vikings'],
    'youngstown state': ['youngstown st.', 'youngstown state', 'youngstown state penguins'],
    'wright state': ['wright st.', 'wright state', 'wright state raiders'],
    
    # Big Sky
    'montana state': ['montana st.', 'montana state', 'montana state bobcats'],
    'idaho state': ['idaho st.', 'idaho state', 'idaho state bengals'],
    'portland state': ['portland st.', 'portland state', 'portland state vikings'],
    'weber state': ['weber st.', 'weber state', 'weber state wildcats'],
    'sacramento state': ['sacramento st.', 'sacramento state', 'sac state', 'sacramento state hornets'],
    
    # Big West
    'long beach state': ['long beach st.', 'long beach state', 'lbsu', 'long beach state beach'],
    
    # MEAC
    'norfolk state': ['norfolk st.', 'norfolk state', 'norfolk state spartans'],
    'coppin state': ['coppin st.', 'coppin state', 'coppin state eagles'],
    'morgan state': ['morgan st.', 'morgan state', 'morgan state bears'],
    
    # OVC
    'southeast missouri state': ['southeast missouri st.', 'southeast missouri state', 'semo', 'semo redhawks'],
    
    # SWAC
    'alcorn state': ['alcorn st.', 'alcorn state', 'alcorn state braves'],
    'mississippi valley state': ['mississippi valley st.', 'miss. valley st.', 'mississippi valley state', 'mvsu', 'mississippi valley state delta devils'],
    
    # Other
    'chicago state': ['chicago st.', 'chicago state', 'chicago state cougars'],
    'washington state': ['washington st.', 'washington state', 'wsu', 'washington state cougars', 'wazzu'],
    'oregon state': ['oregon st.', 'oregon state', 'osu beavers', 'oregon state beavers'],
    'south carolina state': ['s.c. st.', 'sc state', 'south carolina state', 'south carolina st', 'sc state bulldogs'],
}

# Apply all variations to canonical
for canonical, aliases in state_schools.items():
    # Capitalize canonical
    cap_canonical = canonical.title()
    for alias in aliases:
        resolver[alias.lower()] = cap_canonical

print(f"Updated: {len(resolver)} mappings")

# Verify
print("\nVerify key mappings:")
tests = ['michigan st.', 'michigan state', 'ohio st.', 'ohio state', 'penn st.', 'penn state']
for t in tests:
    print(f"  {t} -> {resolver.get(t.lower(), 'NOT FOUND')}")

# Save
with open(resolver_path, 'w') as f:
    json.dump(resolver, f, indent=2, sort_keys=True)

print(f"\nSaved to {resolver_path}")
