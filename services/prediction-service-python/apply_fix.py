from sqlalchemy import create_engine, text
import os

def get_db_url():
    url = os.getenv("DATABASE_URL")
    if url:
        return url.replace("+psycopg2", "")
    
    user = os.getenv("DB_USER", "ncaam")
    host = os.getenv("DB_HOST", "postgres")
    port = os.getenv("DB_PORT", "5432")
    dbname = os.getenv("DB_NAME", "ncaam")
    
    try:
        with open("/run/secrets/db_password", "r") as f:
            password = f.read().strip()
    except FileNotFoundError:
        password = "password" 
        
    return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"

sql = """
DO $$
DECLARE
    target_id UUID;
    bad_id UUID;
BEGIN
    -- Find the REAL team (Cal St. Bakersfield)
    SELECT id INTO target_id FROM teams WHERE canonical_name = 'Cal St. Bakersfield';
    
    -- Find the BAD team (CSU Bakersfield Roadrunners)
    SELECT id INTO bad_id FROM teams WHERE canonical_name = 'CSU Bakersfield Roadrunners';

    IF target_id IS NOT NULL THEN
        RAISE NOTICE 'Found target team Cal St. Bakersfield: %', target_id;
        
        -- Add alias
        INSERT INTO team_aliases (team_id, alias, source)
        VALUES (target_id, 'CSU Bakersfield Roadrunners', 'manual_fix')
        ON CONFLICT (alias, source) DO UPDATE SET team_id = EXCLUDED.team_id;
        
        IF bad_id IS NOT NULL THEN
            RAISE NOTICE 'Found bad team CSU Bakersfield Roadrunners: %', bad_id;
            
            -- Update games referencing bad team
            UPDATE games SET home_team_id = target_id WHERE home_team_id = bad_id;
            UPDATE games SET away_team_id = target_id WHERE away_team_id = bad_id;
            
            -- Delete bad team (optional, but good for cleanup)
            -- DELETE FROM teams WHERE id = bad_id; 
        END IF;
    ELSE
        RAISE NOTICE 'Target team Cal St. Bakersfield NOT FOUND. Trying CSU Bakersfield...';
        SELECT id INTO target_id FROM teams WHERE canonical_name = 'CSU Bakersfield';
        
        IF target_id IS NOT NULL THEN
             RAISE NOTICE 'Found target team CSU Bakersfield: %', target_id;
             -- Add alias
            INSERT INTO team_aliases (team_id, alias, source)
            VALUES (target_id, 'CSU Bakersfield Roadrunners', 'manual_fix')
            ON CONFLICT (alias, source) DO UPDATE SET team_id = EXCLUDED.team_id;
            
            IF bad_id IS NOT NULL THEN
                UPDATE games SET home_team_id = target_id WHERE home_team_id = bad_id;
                UPDATE games SET away_team_id = target_id WHERE away_team_id = bad_id;
            END IF;
        ELSE
            RAISE NOTICE 'Could not find a valid target team for Bakersfield.';
        END IF;
    END IF;
END $$;
"""

try:
    engine = create_engine(get_db_url())
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
        print("Fix applied successfully.")
except Exception as e:
    print(f"Error applying fix: {e}")
