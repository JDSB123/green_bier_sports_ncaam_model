#!/usr/bin/env python3
"""
Simple script to show today's NCAA basketball games
"""
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

# Add the app directory to the path
sys.path.insert(0, 'services/prediction-service-python/app')

try:
    from sqlalchemy import create_engine, text

    # Database connection
    db_password = os.getenv('DB_PASSWORD', 'ncaam')
    db_url = f'postgresql://ncaam:{db_password}@localhost:5450/ncaam'
    engine = create_engine(db_url, pool_pre_ping=True)

    # Get today's date in Chicago time
    chicago_tz = ZoneInfo('America/Chicago')
    today = datetime.now(chicago_tz).date()

    print(f"NCAA Basketball Games - {today}")
    print("=" * 60)

    with engine.connect() as conn:
        # Get today's games
        result = conn.execute(text("""
            SELECT
                g.commence_time,
                ht.canonical_name as home_team,
                at.canonical_name as away_team,
                g.status,
                CASE WHEN hr.team_id IS NOT NULL THEN 'YES' ELSE 'NO' END as home_ratings,
                CASE WHEN ar.team_id IS NOT NULL THEN 'YES' ELSE 'NO' END as away_ratings
            FROM games g
            JOIN teams ht ON g.home_team_id = ht.id
            JOIN teams at ON g.away_team_id = at.id
            LEFT JOIN team_ratings hr ON ht.id = hr.team_id
            LEFT JOIN team_ratings ar ON at.id = ar.team_id
            WHERE DATE(g.commence_time AT TIME ZONE 'America/Chicago') = :today
            ORDER BY g.commence_time
        """), {"today": today})

        games = result.fetchall()

        if not games:
            print("No games scheduled for today.")
            sys.exit(0)

        print(f"Found {len(games)} games:")
        print()

        valid_games = 0
        for game in games:
            commence_time, home_team, away_team, status, home_ratings, away_ratings = game

            game_time = commence_time.astimezone(chicago_tz)
            time_str = game_time.strftime('%I:%M %p CST')

            # Check if both teams have ratings
            has_ratings = home_ratings == '✅' and away_ratings == '✅'
            if has_ratings:
                valid_games += 1

            status_icon = "[SCHEDULED]" if status == "scheduled" else "[IN PROGRESS]"
            ratings_status = f"{home_ratings}/{away_ratings}"

            print(f"{status_icon} {time_str}: {away_team} @ {home_team} [{ratings_status}]")

        print()
        print(f"Games with complete ratings: {valid_games}/{len(games)} ({valid_games/len(games)*100:.1f}%)")
        print()
        print("Legend:")
        print("YES = Team has ratings data")
        print("NO = Team missing ratings data")
        print("[SCHEDULED] = Game scheduled")
        print("[IN PROGRESS] = Game in progress or completed")

except Exception as e:
    print(f"Error connecting to database: {e}")
    print("Make sure the database is running and accessible.")