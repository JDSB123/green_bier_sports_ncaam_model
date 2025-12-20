#!/usr/bin/env python3
"""Fetch box scores for games missing scores."""
import sys
import os
import asyncio
from pathlib import Path
import aiohttp

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.database import Database

async def fetch_box_scores():
    """Fetch box scores for final games missing scores."""
    db = Database()
    db.connect()
    
    # Get API key from environment
    api_key = os.getenv('SPORTSDATA_API_KEY')
    if not api_key:
        print("ERROR: SPORTSDATA_API_KEY not set")
        return
    
    base_url = os.getenv('SPORTSDATA_BASE_URL', 'https://api.sportsdata.io/v3/cfb')
    
    # Get final games without scores
    games = db.fetch_all("""
        SELECT season, week, game_id
        FROM games
        WHERE status = 'Final'
          AND (home_score IS NULL OR away_score IS NULL)
        ORDER BY season, week
        LIMIT 500
    """)
    
    print(f"Found {len(games)} games missing scores")
    
    # Group by season/week for efficient API calls
    week_map = {}
    for game in games:
        key = (game['season'], game['week'])
        if key not in week_map:
            week_map[key] = []
        week_map[key].append(game['game_id'])
    
    updated = 0
    async with aiohttp.ClientSession() as session:
        for (season, week), game_ids in list(week_map.items())[:50]:
            try:
                # Fetch box score for this week
                url = f"{base_url}/stats/json/BoxScoresByWeek/{season}/{week}"
                headers = {'Ocp-Apim-Subscription-Key': api_key}
                
                print(f"Fetching box scores for {season} Week {week} ({len(game_ids)} games)...")
                async with session.get(url, headers=headers, timeout=30) as response:
                    if response.status != 200:
                        print(f"  API returned status {response.status}")
                        continue
                    box_scores = await response.json()
                
                if not box_scores:
                    print(f"  No box scores returned")
                    continue
                
                print(f"  Received {len(box_scores)} box scores")
                
                # Update games with scores
                week_updated = 0
                for box_score in box_scores:
                    # Box score has nested 'Game' object
                    game_data = box_score.get('Game', {})
                    if not game_data:
                        continue
                    
                    game_id = game_data.get('GameID')
                    if not game_id or game_id not in game_ids:
                        continue
                    
                    # Try to get scores from Game object first
                    home_score = game_data.get('HomeScore')
                    away_score = game_data.get('AwayScore')
                    
                    # If not in Game, try TeamGames array
                    if home_score is None or away_score is None:
                        team_games = box_score.get('TeamGames', [])
                        for team_game in team_games:
                            if team_game.get('HomeOrAway') == 'HOME':
                                home_score = team_game.get('Score') or home_score
                            elif team_game.get('HomeOrAway') == 'AWAY':
                                away_score = team_game.get('Score') or away_score
                    
                    if home_score is not None and away_score is not None:
                        # Update game with scores using execute method
                        with db.get_connection() as conn:
                            with conn.cursor() as cur:
                                cur.execute("""
                                    UPDATE games
                                    SET home_score = %s,
                                        away_score = %s,
                                        updated_at = NOW()
                                    WHERE game_id = %s
                                """, (home_score, away_score, game_id))
                                conn.commit()
                        updated += 1
                        week_updated += 1
                        if week_updated <= 3:  # Limit output
                            print(f"  Updated game {game_id}: {away_score}-{home_score}")
                
                if week_updated > 0:
                    print(f"  Updated {week_updated} games for {season} Week {week}")
                else:
                    print(f"  No games updated for {season} Week {week} (checked {len(box_scores)} box scores)")
                
                # Rate limiting
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"  Error fetching week {season}/{week}: {e}")
                import traceback
                traceback.print_exc()
                continue
    
    print(f"\nUpdated {updated} games with scores")
    db.close()

if __name__ == '__main__':
    asyncio.run(fetch_box_scores())
