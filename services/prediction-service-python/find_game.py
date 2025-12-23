from sqlalchemy import create_engine, text
import os

def get_db_url():
    try:
        with open('/run/secrets/db_password', 'r') as f:
            password = f.read().strip()
    except FileNotFoundError:
        password = "password" # Fallback
    
    host = os.getenv("DB_HOST", "postgres")
    user = os.getenv("DB_USER", "ncaam")
    db = os.getenv("DB_NAME", "ncaam")
    return f"postgresql://{user}:{password}@{host}:5432/{db}"

DATABASE_URL = get_db_url()
print(f"Using DB URL: {DATABASE_URL.replace(DATABASE_URL.split(':')[2].split('@')[0], '******')}")

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    # Search for teams
    print("Searching for teams...")
    teams = conn.execute(text("SELECT * FROM teams WHERE canonical_name ILIKE '%Harvard%'")).fetchall()
    for t in teams:
        print(f"Team: {t.canonical_name} (ID: {t.id})")

    # Search for games
    print("\nSearching for games...")
    games = conn.execute(text("""
        SELECT g.id, g.commence_time, ht.canonical_name as home, at.canonical_name as away 
        FROM games g
        JOIN teams ht ON g.home_team_id = ht.id
        JOIN teams at ON g.away_team_id = at.id
        WHERE (ht.canonical_name ILIKE '%Harvard%' OR at.canonical_name ILIKE '%Harvard%')
        AND g.commence_time > NOW() - INTERVAL '2 days'
    """)).fetchall()
    
    if not games:
        print("No games found matching Harvard.")
    else:
        for g in games:
            print(f"Found Game: {g.away} @ {g.home} on {g.commence_time}")
