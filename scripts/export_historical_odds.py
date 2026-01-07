#!/usr/bin/env python3
"""
Export historical odds from PostgreSQL database for backtesting.

This script exports odds_snapshots data from the production database
to CSV files for local ROI simulation testing.

Usage:
    python export_historical_odds.py --start 2022-01-01 --end 2026-01-06
"""

import argparse
import csv
import os
import sys
from datetime import datetime
from pathlib import Path

# Try to load database connection
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)


def get_db_connection():
    """Get database connection from environment or secrets."""
    # Try environment variables first
    db_url = os.environ.get("DATABASE_URL")
    
    if db_url:
        return psycopg2.connect(db_url)
    
    # Try reading from secrets files
    secrets_dir = Path(__file__).resolve().parents[1] / "secrets"
    
    # Check for connection string file
    conn_file = secrets_dir / "database_url.txt"
    if conn_file.exists():
        with open(conn_file) as f:
            return psycopg2.connect(f.read().strip())
    
    # Build from individual secrets
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "ncaam")
    user = os.environ.get("POSTGRES_USER", "postgres")
    
    # Try to read password from secrets
    pw_file = secrets_dir / "db_password.txt"
    if pw_file.exists():
        with open(pw_file) as f:
            password = f.read().strip()
    else:
        password = os.environ.get("POSTGRES_PASSWORD", "")
    
    return psycopg2.connect(
        host=host,
        port=port,
        dbname=db,
        user=user,
        password=password,
    )


def export_odds(start_date: str, end_date: str, output_dir: Path) -> int:
    """Export odds from database to CSV."""
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    query = """
    SELECT 
        os.game_id as event_id,
        g.commence_time,
        g.home_team,
        g.away_team,
        os.bookmaker,
        os.market_type,
        os.period,
        os.point as line,
        os.time as snapshot_time
    FROM odds_snapshots os
    JOIN games g ON os.game_id = g.id
    WHERE g.commence_time >= %s 
      AND g.commence_time < %s
      AND os.market_type IN ('spread', 'total')
    ORDER BY g.commence_time, os.game_id, os.time
    """
    
    cursor.execute(query, (start_date, end_date))
    rows = cursor.fetchall()
    
    if not rows:
        print(f"No odds found between {start_date} and {end_date}")
        return 0
    
    # Group by season
    seasons = {}
    for row in rows:
        commence = row['commence_time']
        # NCAA season: Nov-April = next year's season
        if commence.month >= 11:
            season = commence.year + 1
        else:
            season = commence.year
        
        if season not in seasons:
            seasons[season] = []
        seasons[season].append(row)
    
    # Write per-season files
    total = 0
    for season, season_rows in seasons.items():
        output_file = output_dir / f"odds_{season}.csv"
        
        # Pivot to spread/total format
        games = {}
        for row in season_rows:
            key = (row['event_id'], row['home_team'], row['away_team'], 
                   row['commence_time'].isoformat())
            
            if key not in games:
                games[key] = {
                    'event_id': row['event_id'],
                    'commence_time': row['commence_time'].isoformat(),
                    'home_team': row['home_team'],
                    'away_team': row['away_team'],
                    'bookmaker': row['bookmaker'],
                    'spread': None,
                    'total': None,
                    'h1_spread': None,
                    'h1_total': None,
                    'timestamp': row['snapshot_time'].isoformat() if row['snapshot_time'] else None,
                }
            
            period = row.get('period', 'full')
            market = row['market_type']
            line = row['line']
            
            if period == 'full' or period is None:
                if market == 'spread':
                    games[key]['spread'] = line
                elif market == 'total':
                    games[key]['total'] = line
            elif period == '1h':
                if market == 'spread':
                    games[key]['h1_spread'] = line
                elif market == 'total':
                    games[key]['h1_total'] = line
        
        # Write CSV
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['event_id', 'commence_time', 'home_team', 'away_team', 
                         'bookmaker', 'spread', 'total', 'h1_spread', 'h1_total', 'timestamp']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(games.values())
        
        print(f"Exported {len(games)} games to {output_file}")
        total += len(games)
    
    cursor.close()
    conn.close()
    
    return total


def main():
    parser = argparse.ArgumentParser(description="Export historical odds for backtesting")
    parser.add_argument("--start", type=str, default="2022-01-01",
                       help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default="2026-01-07",
                       help="End date (YYYY-MM-DD)")
    parser.add_argument("--output", type=str, default=None,
                       help="Output directory")
    args = parser.parse_args()
    
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = Path(__file__).resolve().parents[1] / "testing" / "data" / "historical_odds"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Exporting odds from {args.start} to {args.end}")
    print(f"Output directory: {output_dir}")
    
    try:
        total = export_odds(args.start, args.end, output_dir)
        print(f"\nTotal: {total} games exported")
    except Exception as e:
        print(f"ERROR: {e}")
        print("\nMake sure DATABASE_URL is set or secrets/db_password.txt exists")
        sys.exit(1)


if __name__ == "__main__":
    main()
