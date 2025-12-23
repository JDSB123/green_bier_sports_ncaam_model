from sqlalchemy import create_engine, text
import os

DATABASE_URL = os.getenv("DATABASE_URL", "").replace("+psycopg2", "")
if not DATABASE_URL:
    # Fallback for local testing if env var not set
    DATABASE_URL = "postgresql://ncaam:password@postgres:5432/ncaam"

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    # Search for teams
    print("Searching for teams...")
    teams = conn.execute(text("SELECT * FROM teams WHERE canonical_name ILIKE '%Idaho%' OR canonical_name ILIKE '%Bakersfield%'")).fetchall()
    for t in teams:
        print(f"Team: {t.canonical_name} (ID: {t.id})")

    # Search for games
    print("\nSearching for games...")
    games = conn.execute(text("""
        SELECT g.id, g.commence_time, ht.canonical_name as home, at.canonical_name as away 
        FROM games g
        JOIN teams ht ON g.home_team_id = ht.id
        JOIN teams at ON g.away_team_id = at.id
        WHERE (ht.canonical_name ILIKE '%Idaho%' OR at.canonical_name ILIKE '%Idaho%')
        AND (ht.canonical_name ILIKE '%Bakersfield%' OR at.canonical_name ILIKE '%Bakersfield%')
        AND g.commence_time > NOW() - INTERVAL '2 days'
    """)).fetchall()
    
    if not games:
        print("No games found matching both teams.")
        # List ALL games for Idaho or Bakersfield
        print("\nAll games for Idaho or Bakersfield:")
        games = conn.execute(text("""
            SELECT g.id, g.commence_time, ht.canonical_name as home, at.canonical_name as away 
            FROM games g
            JOIN teams ht ON g.home_team_id = ht.id
            JOIN teams at ON g.away_team_id = at.id
            WHERE ((ht.canonical_name ILIKE '%Idaho%' OR at.canonical_name ILIKE '%Idaho%')
               OR (ht.canonical_name ILIKE '%Bakersfield%' OR at.canonical_name ILIKE '%Bakersfield%'))
            AND g.commence_time > NOW() - INTERVAL '2 days'
            ORDER BY g.commence_time
        """)).fetchall()
        for g in games:
            print(f"Game: {g.away} @ {g.home} on {g.commence_time}")
    else:
        for g in games:
            print(f"Found Game: {g.away} @ {g.home} on {g.commence_time}")
