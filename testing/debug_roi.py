"""Debug script for ROI simulator."""
import sys
import csv

sys.path.insert(0, '.')
sys.path.insert(0, 'C:/Users/JB/green-bier-ventures/NCAAM_main/services/prediction-service-python/src')

from production_parity.roi_simulator import ROISimulator

sim = ROISimulator()
sim.load_historical_odds()

games_file = 'data/historical/games_2024.csv'
games_processed = 0
games_with_odds = 0
fail_reasons = {}

with open(games_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        games_processed += 1
        try:
            game_date = row.get('date', '')
            home_team_raw = row.get('home_team', '')
            away_team_raw = row.get('away_team', '')
            home_score = int(row.get('home_score', 0))
            away_score = int(row.get('away_score', 0))
            
            # Get H1 scores
            h1_home_str = row.get('h1_home', '')
            h1_away_str = row.get('h1_away', '')
            h1_home = int(float(h1_home_str)) if h1_home_str else None
            h1_away = int(float(h1_away_str)) if h1_away_str else None
            
            # Resolve team names
            home_team = sim.team_resolver.resolve(home_team_raw)
            away_team = sim.team_resolver.resolve(away_team_raw)
            
            if not home_team or not away_team:
                fail_reasons['team_resolve'] = fail_reasons.get('team_resolve', 0) + 1
                continue
            
            # Find odds
            odds = sim.find_odds(home_team_raw, away_team_raw, game_date)
            if not odds:
                fail_reasons['no_odds'] = fail_reasons.get('no_odds', 0) + 1
                continue
            
            games_with_odds += 1
            
            # Check ratings
            home_result = sim.ratings_loader.get_ratings_for_game(home_team_raw, game_date)
            away_result = sim.ratings_loader.get_ratings_for_game(away_team_raw, game_date)
            
            if not home_result.found or not away_result.found:
                fail_reasons['no_ratings'] = fail_reasons.get('no_ratings', 0) + 1
                continue
            
        except Exception as e:
            fail_reasons['exception'] = fail_reasons.get('exception', 0) + 1
            if fail_reasons['exception'] <= 3:
                print(f'Exception: {e}')

print(f'Processed: {games_processed}')
print(f'With odds: {games_with_odds}')
print(f'Fail reasons: {fail_reasons}')
