#!/usr/bin/env python3
"""Apply migration 023 to Azure database."""

import psycopg2

DATABASE_URL = "postgres://ncaam:NcaamProd2026!@ncaam-stable-gbsv-postgres.postgres.database.azure.com:5432/ncaam?sslmode=require"

# Split into separate statements
MIGRATION_PART1 = """
-- Migration 023: Centralized Team Name Normalization
CREATE OR REPLACE FUNCTION normalize_team_name_input(input_name TEXT)
RETURNS TEXT AS $$
DECLARE
    normalized TEXT;
BEGIN
    normalized := TRIM(input_name);
    IF normalized IS NULL OR normalized = '' THEN
        RETURN normalized;
    END IF;

    -- State -> St.
    normalized := REGEXP_REPLACE(normalized, ' State$', ' St.', 'i');
    normalized := REGEXP_REPLACE(normalized, ' State ', ' St. ', 'gi');

    -- Saint -> St.
    normalized := REGEXP_REPLACE(normalized, '^Saint ', 'St. ', 'i');
    normalized := REGEXP_REPLACE(normalized, '^St ', 'St. ', 'i');

    -- Directional abbreviations
    normalized := REGEXP_REPLACE(normalized, '^Northern ', 'N. ', 'i');
    normalized := REGEXP_REPLACE(normalized, '^Southern ', 'S. ', 'i');
    normalized := REGEXP_REPLACE(normalized, '^Eastern ', 'E. ', 'i');
    normalized := REGEXP_REPLACE(normalized, '^Western ', 'W. ', 'i');
    normalized := REGEXP_REPLACE(normalized, '^Central ', 'C. ', 'i');

    -- Carolina abbreviations
    normalized := REGEXP_REPLACE(normalized, '^North Carolina', 'N.C.', 'i');
    normalized := REGEXP_REPLACE(normalized, '^South Carolina', 'S.C.', 'i');

    -- Other common abbreviations
    normalized := REGEXP_REPLACE(normalized, ' University$', '', 'i');
    normalized := REGEXP_REPLACE(normalized, '^University of ', '', 'i');

    -- Normalize quotes and dashes
    normalized := REPLACE(normalized, E'\\u2019', '''');
    normalized := REPLACE(normalized, E'\\u201C', '"');
    normalized := REPLACE(normalized, E'\\u201D', '"');
    normalized := REPLACE(normalized, E'\\u2013', '-');
    normalized := REPLACE(normalized, E'\\u2014', '-');

    -- Collapse multiple spaces
    normalized := REGEXP_REPLACE(normalized, '\\s+', ' ', 'g');

    RETURN TRIM(normalized);
END;
$$ LANGUAGE plpgsql IMMUTABLE;
"""

MIGRATION_PART2 = """
CREATE OR REPLACE FUNCTION resolve_team_name(input_name TEXT)
RETURNS TEXT AS $$
DECLARE
    v_result TEXT;
    v_normalized TEXT;
BEGIN
    IF input_name IS NULL OR TRIM(input_name) = '' THEN
        RETURN NULL;
    END IF;

    -- STEP 1: Exact match on canonical_name
    SELECT t.canonical_name INTO v_result
    FROM teams t
    LEFT JOIN team_ratings tr ON t.id = tr.team_id
    WHERE LOWER(t.canonical_name) = LOWER(TRIM(input_name))
    ORDER BY tr.team_id IS NOT NULL DESC
    LIMIT 1;
    IF v_result IS NOT NULL THEN RETURN v_result; END IF;

    -- STEP 2: Exact match on alias
    SELECT t.canonical_name INTO v_result
    FROM teams t
    JOIN team_aliases ta ON t.id = ta.team_id
    LEFT JOIN team_ratings tr ON t.id = tr.team_id
    WHERE LOWER(ta.alias) = LOWER(TRIM(input_name))
    ORDER BY tr.team_id IS NOT NULL DESC
    LIMIT 1;
    IF v_result IS NOT NULL THEN RETURN v_result; END IF;

    -- STEP 3: Apply normalization and try again
    v_normalized := normalize_team_name_input(input_name);
    IF v_normalized IS DISTINCT FROM TRIM(input_name) THEN
        SELECT t.canonical_name INTO v_result
        FROM teams t
        LEFT JOIN team_ratings tr ON t.id = tr.team_id
        WHERE LOWER(t.canonical_name) = LOWER(v_normalized)
        ORDER BY tr.team_id IS NOT NULL DESC
        LIMIT 1;
        IF v_result IS NOT NULL THEN RETURN v_result; END IF;

        SELECT t.canonical_name INTO v_result
        FROM teams t
        JOIN team_aliases ta ON t.id = ta.team_id
        LEFT JOIN team_ratings tr ON t.id = tr.team_id
        WHERE LOWER(ta.alias) = LOWER(v_normalized)
        ORDER BY tr.team_id IS NOT NULL DESC
        LIMIT 1;
        IF v_result IS NOT NULL THEN RETURN v_result; END IF;
    END IF;

    -- STEP 4: Mascot stripping
    v_normalized := REGEXP_REPLACE(TRIM(input_name),
        ' (Wildcats|Bulldogs|Tigers|Eagles|Bears|Lions|Panthers|Hawks|Huskies|Cougars|Cardinals|Blue Devils|Tar Heels|Volunteers|Jayhawks|Spartans|Wolverines|Buckeyes|Boilermakers|Seminoles|Cavaliers|Hoosiers|Badgers|Hawkeyes|Cyclones|Mountaineers|Longhorns|Sooners|Cowboys|Aggies|Bruins|Trojans|Beavers|Ducks|Gators|Crimson Tide|Fighting Irish|Demon Deacons|Yellow Jackets|Hokies|Terrapins|Nittany Lions|Scarlet Knights|Rockets|Bobcats|Broncos|Owls|Colonels|Governors|Hatters|Grizzlies|Roadrunners|Matadors|Lumberjacks|Mustangs|Wolf Pack|Aztecs|Falcons|Miners|Gaels|Pilots|Waves|Toreros|Leopards|Raiders|Catamounts|Great Danes|Seawolves|Retrievers|Flames|Monarchs|Dukes|Spiders|Rams|Bonnies|Explorers|Jaspers|Peacocks|Stags|Musketeers|Bearcats|Flyers|Hoyas|Friars|Pirates|Bluejays|Shockers|Braves|Coyotes|Penguins|Vikings|Hornets|Rattlers|Jaguars|Dolphins)$',
        '', 'i');

    IF v_normalized IS DISTINCT FROM TRIM(input_name) THEN
        v_normalized := normalize_team_name_input(v_normalized);
        SELECT t.canonical_name INTO v_result
        FROM teams t
        LEFT JOIN team_ratings tr ON t.id = tr.team_id
        WHERE LOWER(t.canonical_name) = LOWER(v_normalized)
        ORDER BY tr.team_id IS NOT NULL DESC
        LIMIT 1;
        IF v_result IS NOT NULL THEN RETURN v_result; END IF;
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE;
"""

MIGRATION_PART3 = """
INSERT INTO schema_migrations (filename, applied_at)
VALUES ('023_centralized_normalization.sql', NOW())
ON CONFLICT (filename) DO NOTHING;
"""

def main():
    print("Connecting to Azure Postgres...")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    print("Applying normalize_team_name_input function...")
    cur.execute(MIGRATION_PART1)

    print("Applying resolve_team_name function...")
    cur.execute(MIGRATION_PART2)

    print("Recording migration...")
    cur.execute(MIGRATION_PART3)

    conn.commit()

    # Test
    print("\nTesting resolve_team_name:")
    test_cases = [
        ('Florida State', 'Florida St.'),
        ('Duke Blue Devils', 'Duke'),
        ('UConn', 'Connecticut'),
        ('Michigan State Spartans', 'Michigan St.'),
    ]

    for input_name, expected in test_cases:
        cur.execute("SELECT resolve_team_name(%s)", (input_name,))
        result = cur.fetchone()[0]
        status = "OK" if result == expected else f"FAIL (got {result})"
        print(f"  {input_name} -> {result} [{status}]")

    cur.close()
    conn.close()
    print("\nMigration 023 applied successfully!")

if __name__ == "__main__":
    main()
