"""Find EXACT team names in training for problem matchups."""
import pandas as pd
import json

training = pd.read_csv('../services/prediction-service-python/training_data/training_data_with_odds.csv')
games_all = pd.read_csv('data/historical/games_all.csv')

# Check what teams appear on 2024-01-03
date = '2024-01-03'
games_on_date = training[training['game_date'] == date]
print(f"Training games on {date}: {len(games_on_date)}")
for _, row in games_on_date.iterrows():
    print(f"  {row['home_team']} vs {row['away_team']}")

print()

# Check for Bowling Green on this date
bg_games = training[training['home_team'].str.contains('Bowling', case=False, na=False) | 
                    training['away_team'].str.contains('Bowling', case=False, na=False)]
print(f"All Bowling Green games in training: {len(bg_games)}")
if len(bg_games) > 0:
    print(bg_games[['game_date', 'home_team', 'away_team']].head(5))

# Check for Loyola Maryland
loyola_games = training[training['home_team'].str.contains('Loyola', case=False, na=False) | 
                        training['away_team'].str.contains('Loyola', case=False, na=False)]
print(f"\nAll Loyola games in training: {len(loyola_games)}")
print("Sample:")
for team in loyola_games['home_team'].unique()[:10]:
    if 'Loyola' in team:
        print(f"  {team}")
for team in loyola_games['away_team'].unique()[:10]:
    if 'Loyola' in team:
        print(f"  {team}")

# Check for IPFW/Fort Wayne
fw_games = training[(training['home_team'].str.contains('Wayne', case=False, na=False)) | 
                    (training['away_team'].str.contains('Wayne', case=False, na=False)) |
                    (training['home_team'].str.contains('IPFW', case=False, na=False)) |
                    (training['away_team'].str.contains('IPFW', case=False, na=False))]
print(f"\nAll Fort Wayne/IPFW games in training: {len(fw_games)}")
if len(fw_games) > 0:
    print("Teams used:")
    print(set(fw_games['home_team'].tolist() + fw_games['away_team'].tolist()))
