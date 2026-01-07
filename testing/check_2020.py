import pandas as pd
games_all = pd.read_csv('data/historical/games_all.csv')

# Get 2020-2021 season (Nov 2020 - Apr 2021)
games_2020 = games_all[(games_all['date'] >= '2020-11-01') & (games_all['date'] <= '2021-04-30')]
print(f'games_all 2020-21 season: {len(games_2020)} games')
print(f'Date range: {games_2020["date"].min()} to {games_2020["date"].max()}')
print()
print('Sample teams:')
print(games_2020[['date', 'home_team', 'away_team']].head(10))
