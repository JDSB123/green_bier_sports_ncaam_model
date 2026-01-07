"""Find exact team names in training for problem teams."""
import pandas as pd

training = pd.read_csv('../services/prediction-service-python/training_data/training_data_with_odds.csv')
games_all = pd.read_csv('data/historical/games_all.csv')

# Combine all teams
all_teams = set(training['home_team'].unique()) | set(training['away_team'].unique())
all_teams |= set(games_all['home_team'].unique()) | set(games_all['away_team'].unique())

# Problem searches
searches = [
    ('ut martin', 'martin'),
    ('ualr', 'little rock'),
    ('miss valley', 'mississippi valley'),
    ('ipfw', 'fort wayne', 'purdue'),
    ('loyola maryland', 'loyola md'),
    ('miami fl', 'miami hurricanes'),
    ('utrgv', 'rio grande'),
    ('southeast missouri', 'semo'),
    ('belmont',),
    ('lamar',),
    ('tennessee state', 'tennessee st'),
    ('tennessee tech',),
    ('nicholls',),
    ('washington state', 'washington st'),
]

print("EXACT team names in training data:")
for search_terms in searches:
    matches = []
    for team in all_teams:
        for term in search_terms:
            if term.lower() in team.lower():
                matches.append(team)
                break
    if matches:
        # Get unique
        matches = list(set(matches))
        print(f"  {search_terms[0]}: {matches[:5]}")
    else:
        print(f"  {search_terms[0]}: NO MATCHES")
