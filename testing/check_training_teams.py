"""Check what training data actually uses for problem teams."""
import pandas as pd

training = pd.read_csv('../services/prediction-service-python/training_data/training_data_with_odds.csv')
games_all = pd.read_csv('data/historical/games_all.csv')

# What does training actually use for these teams?
search_terms = ['fort wayne', 'ipfw', 'ualr', 'little rock', 'loyola', 
                'ut martin', 'martin', 'utrgv', 'rio grande', 'miami',
                'mississippi valley', 'miss valley', 'mvsu']

all_teams = set(training['home_team'].unique()) | set(training['away_team'].unique())
all_teams |= set(games_all['home_team'].unique()) | set(games_all['away_team'].unique())

for term in search_terms:
    matches = [t for t in all_teams if term.lower() in t.lower()]
    if matches:
        print(f'{term}: {matches}')
    else:
        print(f'{term}: NO MATCHES')
