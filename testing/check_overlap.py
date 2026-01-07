"""Check overlap between odds data and game scores."""
import csv
from pathlib import Path
from collections import defaultdict

# Load odds data
with open('data/historical_odds/odds_consolidated_canonical.csv', 'r') as f:
    odds = list(csv.DictReader(f))
print(f'Odds games: {len(odds):,}')

# Build lookup key: canonical_home + canonical_away + date
odds_keys = set()
for r in odds:
    key = f"{r['home_team_canonical']}|{r['away_team_canonical']}|{r['game_date']}"
    odds_keys.add(key)
print(f'Unique odds game keys: {len(odds_keys):,}')

# Load all game scores
scores = []
for f in sorted(Path('data/historical').glob('games_20*.csv')):
    with open(f, 'r') as file:
        scores.extend(list(csv.DictReader(file)))
print(f'Score games: {len(scores):,}')
print(f'Score columns: {list(scores[0].keys())}')

# Need to canonicalize score team names to match
from production_parity.team_resolver import ProductionTeamResolver
resolver = ProductionTeamResolver()

# Build score lookup
score_keys = set()
score_by_key = {}
unmatched_score_teams = set()

for r in scores:
    # Resolve team names
    home_result = resolver.resolve(r['home_team'])
    away_result = resolver.resolve(r['away_team'])
    
    if home_result.resolved and away_result.resolved:
        home_canon = home_result.canonical_name
        away_canon = away_result.canonical_name
        date = r['date']  # Format: YYYY-MM-DD
        key = f"{home_canon}|{away_canon}|{date}"
        score_keys.add(key)
        score_by_key[key] = r
    else:
        if not home_result.resolved:
            unmatched_score_teams.add(r['home_team'])
        if not away_result.resolved:
            unmatched_score_teams.add(r['away_team'])

print(f'Score games with canonical teams: {len(score_keys):,}')

# Find overlap
overlap = odds_keys & score_keys
print(f'\n*** OVERLAP (games with both odds AND scores): {len(overlap):,} ***')

# Missing from each side
in_odds_not_scores = odds_keys - score_keys
in_scores_not_odds = score_keys - odds_keys

print(f'Games with odds but no scores: {len(in_odds_not_scores):,}')
print(f'Games with scores but no odds: {len(in_scores_not_odds):,}')

# Break down overlap by season
by_season = defaultdict(int)
for key in overlap:
    parts = key.split('|')
    date = parts[2]
    year = int(date[:4])
    month = int(date[5:7])
    season = year + 1 if month >= 11 else year
    by_season[season] += 1

print('\nOverlap by season:')
for season in sorted(by_season.keys()):
    print(f'  {season-1}-{str(season)[2:]}: {by_season[season]:,} games')

# Show some unmatched score teams
if unmatched_score_teams:
    print(f'\nUnmatched teams in score data ({len(unmatched_score_teams)}):')
    for team in sorted(unmatched_score_teams)[:20]:
        print(f'  - {team}')
