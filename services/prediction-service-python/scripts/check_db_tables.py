#!/usr/bin/env python3
"""Check database tables and Barttorvik data."""
import os
from pathlib import Path
from sqlalchemy import create_engine, text

# Build connection from environment
pw_file = Path('/run/secrets/db_password')
password = pw_file.read_text().strip() if pw_file.exists() else os.environ.get('DB_PASSWORD', 'ncaam')
db_host = os.environ.get('DB_HOST', 'postgres')
db_user = os.environ.get('DB_USER', 'ncaam')
db_name = os.environ.get('DB_NAME', 'ncaam')
db_port = os.environ.get('DB_PORT', '5432')
db_url = f'postgresql://{db_user}:{password}@{db_host}:{db_port}/{db_name}'

engine = create_engine(db_url)

with engine.connect() as conn:
    print("=" * 60)
    print("DATABASE TABLES")
    print("=" * 60)
    
    result = conn.execute(text("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' ORDER BY table_name
    """))
    for row in result:
        print(f"  - {row[0]}")
    
    print("\n" + "=" * 60)
    print("TEAM RATINGS")
    print("=" * 60)
    
    result = conn.execute(text("""
        SELECT COUNT(*), 
               MIN(rating_date) as min_date, 
               MAX(rating_date) as max_date,
               COUNT(DISTINCT rating_date) as unique_dates
        FROM team_ratings
    """))
    row = result.fetchone()
    print(f"  Records: {row[0]}")
    print(f"  Date range: {row[1]} to {row[2]}")
    print(f"  Unique dates: {row[3]}")
    
    # Check columns in team_ratings
    result = conn.execute(text("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'team_ratings' ORDER BY ordinal_position
    """))
    print("\n  Columns:")
    for row in result:
        print(f"    - {row[0]}")
    
    # Check if there's a barttorvik_raw table
    print("\n" + "=" * 60)
    print("BARTTORVIK RAW DATA")
    print("=" * 60)
    
    result = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'barttorvik_raw'
        )
    """))
    has_raw = result.scalar()
    
    if has_raw:
        result = conn.execute(text("""
            SELECT COUNT(*), 
                   MIN(captured_at) as min_date, 
                   MAX(captured_at) as max_date
            FROM barttorvik_raw
        """))
        row = result.fetchone()
        print(f"  Records: {row[0]}")
        print(f"  Date range: {row[1]} to {row[2]}")
    else:
        print("  Table 'barttorvik_raw' does not exist")
    
    # Sample team ratings
    print("\n" + "=" * 60)
    print("SAMPLE TEAM RATINGS")
    print("=" * 60)
    
    result = conn.execute(text("""
        SELECT team_id, adj_o, adj_d, tempo, barthag, rank, rating_date
        FROM team_ratings 
        ORDER BY rank LIMIT 10
    """))
    print(f"  {'Team':<30} {'AdjO':>6} {'AdjD':>6} {'Tempo':>6} {'Barthag':>8} {'Rank':>5}")
    print("  " + "-" * 70)
    for row in result:
        print(f"  {row[0]:<30} {row[1]:>6.1f} {row[2]:>6.1f} {row[3]:>6.1f} {row[4]:>8.3f} {row[5]:>5}")
