"""Check when problem teams appear in training."""
import pandas as pd

training = pd.read_csv('../services/prediction-service-python/training_data/training_data_with_odds.csv')

searches = {
    'UALR / Little Rock': ['ualr', 'little rock'],
    'IPFW / Fort Wayne': ['ipfw', 'fort wayne', 'purdue fort'],
    'UTRGV / Rio Grande': ['utrgv', 'rio grande'],
    'Miss Valley St': ['mississippi valley', 'miss valley'],
}

print("When problem teams appear in training:")
for label, terms in searches.items():
    mask = pd.Series([False] * len(training))
    for term in terms:
        mask |= (training['home_team'].str.contains(term, case=False, na=False) | 
                 training['away_team'].str.contains(term, case=False, na=False))
    matches = training[mask]
    if len(matches) > 0:
        print(f"\n{label}: {len(matches)} games")
        print(f"  Date range: {matches['game_date'].min()} to {matches['game_date'].max()}")
        # Show sample
        for _, row in matches.head(3).iterrows():
            print(f"    {row['game_date']}: {row['home_team']} vs {row['away_team']}")
    else:
        print(f"\n{label}: NO MATCHES")
