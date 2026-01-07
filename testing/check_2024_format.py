"""Check what format training uses for recent games."""
import pandas as pd

training = pd.read_csv('../services/prediction-service-python/training_data/training_data_with_odds.csv')

# Check 2024 games for problem teams
training_2024 = training[training['game_date'] >= '2024-01-01']

searches = {
    'ut martin': 'martin',
    'ualr': 'little rock',
    'miss valley': 'mississippi',
    'ipfw': 'fort wayne',
    'loyola maryland': 'loyola',
    'miami': 'miami',
    'utrgv': 'rio grande',
}

print("Team names used in 2024 training data:")
for label, term in searches.items():
    # Find games with this term
    mask = (training_2024['home_team'].str.contains(term, case=False, na=False) | 
            training_2024['away_team'].str.contains(term, case=False, na=False))
    matches = training_2024[mask]
    if len(matches) > 0:
        # Get unique team names
        teams = set()
        for _, row in matches.iterrows():
            if term.lower() in row['home_team'].lower():
                teams.add(row['home_team'])
            if term.lower() in row['away_team'].lower():
                teams.add(row['away_team'])
        print(f"  {label}: {list(teams)[:3]}")
    else:
        print(f"  {label}: NO MATCHES in 2024")
