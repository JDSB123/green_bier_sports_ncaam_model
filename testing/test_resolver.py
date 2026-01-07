"""Test the team resolver for specific teams."""
from production_parity.team_resolver import ProductionTeamResolver

# Also check non_d1 filter
try:
    from production_parity.non_d1_filter import is_non_d1_team
    has_filter = True
except ImportError:
    has_filter = False
    print("No non_d1_filter available")

resolver = ProductionTeamResolver()

# Test the failing teams
test_teams = [
    'Detroit Mercy Titans',
    'detroit mercy titans',
    'Detroit Mercy',  # Should work 
    'detroit mercy',  # Should work
    'UT Rio Grande Valley Vaqueros',
    'ut rio grande valley vaqueros',
    'IUPUI Jaguars',
    'iupui jaguars',
    'Tulane Green Wave',
    'tulane green wave',
    'Mercyhurst Lakers',
    'mercyhurst lakers',
    'West Georgia Wolves',
    'west georgia wolves'
]

print(f"\nHas non-D1 filter: {has_filter}")
if has_filter:
    print("\nChecking if teams are filtered as non-D1:")
    for team in test_teams:
        is_blocked = is_non_d1_team(team)
        print(f"  {team}: {'BLOCKED as non-D1' if is_blocked else 'NOT blocked'}")

print("\nResolving teams:")
for team in test_teams:
    result = resolver.resolve(team)
    if result.resolved:
        print(f"OK '{team}' -> '{result.canonical_name}' (step: {result.step_used.value})")
    else:
        print(f"XX '{team}' -> UNMATCHED (step: {result.step_used.value})")
