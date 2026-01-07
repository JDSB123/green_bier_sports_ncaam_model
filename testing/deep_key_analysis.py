"""Find exact reason for gaps - deep dive on key matching."""
import pandas as pd
import json

with open('../services/prediction-service-python/training_data/team_aliases_db.json', 'r') as f:
    resolver = json.load(f)

def norm(name):
    if not name or pd.isna(name): return ''
    return resolver.get(str(name).lower().strip(), name)

# Load all sources
training = pd.read_csv('../services/prediction-service-python/training_data/training_data_with_odds.csv')
games_all = pd.read_csv('data/historical/games_all.csv')
h1_games = pd.read_csv('data/h1_historical/h1_games_all.csv')
odds = pd.read_csv('data/historical_odds/odds_consolidated_canonical.csv')

print("=== BUILD TRAINING KEYS ===")
training_keys = set()
for _, row in training.iterrows():
    date = str(row['game_date'])[:10]
    home = norm(row['home_team'] if 'home_team' in row else '')
    away = norm(row['away_team'] if 'away_team' in row else '')
    if home and away:
        training_keys.add((date, home, away))
        
print(f"Training keys: {len(training_keys)}")

print("\n=== BUILD GAMES_ALL KEYS ===")
games_keys = set()
for _, row in games_all.iterrows():
    date = str(row['date'])[:10]
    home = norm(row['home_team'] if 'home_team' in row else '')
    away = norm(row['away_team'] if 'away_team' in row else '')
    if home and away:
        games_keys.add((date, home, away))

print(f"games_all keys: {len(games_keys)}")

print("\n=== COMBINED SCORE KEYS ===")
all_score_keys = training_keys | games_keys
print(f"Combined keys: {len(all_score_keys)}")

print("\n=== BUILD ODDS KEYS ===")
odds_keys = set()
for _, row in odds.iterrows():
    date = str(row['game_date'])[:10]
    home = norm(row['home_team'] if 'home_team' in row else '')
    away = norm(row['away_team'] if 'away_team' in row else '')
    if home and away:
        odds_keys.add((date, home, away))

print(f"Odds keys: {len(odds_keys)}")

print("\n=== MATCHING ===")
matches = odds_keys & all_score_keys
print(f"Odds games that match score data: {len(matches)} / {len(odds_keys)} = {len(matches)/len(odds_keys)*100:.1f}%")

unmatched = odds_keys - all_score_keys
print(f"Unmatched odds games: {len(unmatched)}")

# Sample unmatched
print("\n=== SAMPLE UNMATCHED GAMES (2023-2024) ===")
unmatched_recent = [k for k in unmatched if k[0].startswith('2023') or k[0].startswith('2024')]
for k in sorted(unmatched_recent)[:20]:
    print(f"  {k[0]}: {k[1]} vs {k[2]}")
    # Look for similar in score data
    date_matches = [sk for sk in all_score_keys if sk[0] == k[0]]
    for sk in date_matches:
        if k[1].lower()[:5] in sk[1].lower() or k[2].lower()[:5] in sk[2].lower():
            print(f"    Similar: {sk[1]} vs {sk[2]}")
