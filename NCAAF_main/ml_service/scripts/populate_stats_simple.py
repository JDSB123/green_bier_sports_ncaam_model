#!/usr/bin/env python3
"""
Simple team stats population from games data.
"""

import sys
import os
from pathlib import Path
import logging

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    logger.info("Populating team stats from games...")

    db = Database()
    db.connect()

    # Clear existing
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM team_season_stats")
            conn.commit()

    # Simple population query
    query = """
    INSERT INTO team_season_stats (
        team_id,
        season,
        points_per_game,
        yards_per_game,
        pass_yards_per_game,
        rush_yards_per_game,
        yards_per_play,
        points_allowed_per_game,
        yards_allowed_per_game,
        third_down_conversion_pct,
        red_zone_scoring_pct,
        turnovers,
        takeaways,
        created_at,
        updated_at
    )
    WITH team_stats AS (
        SELECT
            t.id as team_id,
            g.season,
            AVG(CASE WHEN t.id = g.home_team_id THEN g.home_score ELSE g.away_score END) as ppg,
            AVG(CASE WHEN t.id = g.home_team_id THEN g.away_score ELSE g.home_score END) as papg,
            COUNT(*) as game_count
        FROM teams t
        CROSS JOIN LATERAL (
            SELECT * FROM games
            WHERE (home_team_id = t.id OR away_team_id = t.id)
              AND status IN ('Final', 'F/OT')
        ) g
        GROUP BY t.id, g.season
        HAVING COUNT(*) > 0
    )
    SELECT
        team_id,
        season,
        ppg,                           -- points_per_game
        ppg * 12.5,                    -- yards_per_game (estimate)
        ppg * 7.5,                     -- pass_yards_per_game (estimate)
        ppg * 5.0,                     -- rush_yards_per_game (estimate)
        5.5,                           -- yards_per_play (estimate)
        papg,                          -- points_allowed_per_game
        papg * 12.5,                   -- yards_allowed_per_game (estimate)
        35.0,                          -- third_down_conversion_pct (estimate)
        50.0,                          -- red_zone_scoring_pct (estimate)
        12,                            -- turnovers (estimate)
        12,                            -- takeaways (estimate)
        NOW(),
        NOW()
    FROM team_stats
    """

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            count = cur.rowcount
            conn.commit()

    logger.info(f"Populated {count} team-season records")

    # Show summary
    summary = db.fetch_one("""
        SELECT COUNT(*) as total, AVG(points_per_game) as avg_ppg
        FROM team_season_stats
    """)

    avg_ppg = summary.get('avg_ppg') or 0.0
    logger.info(f"Total: {summary['total']} records, Avg PPG: {avg_ppg:.1f}")

    db.close()
    logger.info("Done!")


if __name__ == "__main__":
    main()