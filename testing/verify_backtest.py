"""Quick verification of rebuilt backtest data."""
import pandas as pd

df = pd.read_csv('data/backtest_complete.csv')
print(f"Total games: {len(df)}")
print(f"With spread: {df['spread'].notna().sum()}")
print(f"With scores: {df['home_score'].notna().sum()}")
print()

# By season
df['year'] = pd.to_datetime(df['game_date']).dt.year
df['month'] = pd.to_datetime(df['game_date']).dt.month
df['season'] = df.apply(lambda x: f"{x['year']}-{x['year']+1}" if x['month'] >= 8 else f"{x['year']-1}-{x['year']}", axis=1)

print("By Season:")
for season in sorted(df['season'].unique()):
    subset = df[df['season'] == season]
    with_odds = subset['spread'].notna().sum()
    pct = int(with_odds * 100 / len(subset))
    print(f"  {season}: {len(subset)} games, {with_odds} with odds ({pct}%)")
