import pandas as pd
training = pd.read_csv('../services/prediction-service-python/training_data/training_data_with_odds.csv')

# Check for Bowling Green vs Eastern Michigan
bg_em = training[((training['home_team'].str.contains('Bowling', case=False, na=False)) & 
                  (training['away_team'].str.contains('Eastern Mich', case=False, na=False))) |
                 ((training['away_team'].str.contains('Bowling', case=False, na=False)) & 
                  (training['home_team'].str.contains('Eastern Mich', case=False, na=False)))]
print(f'Bowling Green vs Eastern Michigan games: {len(bg_em)}')
if len(bg_em) > 0:
    print(bg_em[['game_date', 'home_team', 'away_team']])

# Check all games on 2024-01-03 in odds
odds = pd.read_csv('data/historical_odds/odds_consolidated_canonical.csv')
odds_date = odds[odds['game_date'] == '2024-01-03']
print(f'\nOdds on 2024-01-03: {len(odds_date)} games')
for _, row in odds_date.head(10).iterrows():
    print(f"  {row['home_team']} vs {row['away_team']}")
