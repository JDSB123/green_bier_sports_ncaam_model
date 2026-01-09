-- Migration 023: Centralized Team Name Normalization
--
-- Moves normalization rules from Go/Rust code into the database.
-- This ensures consistent name handling across ALL services without code changes.
--
-- Previously, each service had its own normalization:
--   - Go (ratings-sync): State→St., Saint→St., Northern→N., etc.
--   - Rust (odds-ingestion): State→St., quote normalization
--   - Python (odds_sync): TEAM_NAME_ALIASES dict
--
-- Now: resolve_team_name() applies these rules automatically.

-- Step 1: Create normalization function that applies all standard transformations
CREATE OR REPLACE FUNCTION normalize_team_name_input(input_name TEXT)
RETURNS TEXT AS $$
DECLARE
    normalized TEXT;
BEGIN
    -- Start with trimmed input
    normalized := TRIM(input_name);

    -- Exit early for NULL/empty
    IF normalized IS NULL OR normalized = '' THEN
        RETURN normalized;
    END IF;

    -- Standard abbreviations (order matters!)
    -- These match the Go/Rust normalization rules

    -- State -> St. (most common)
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

    -- Normalize quotes and dashes (from Rust)
    normalized := REPLACE(normalized, ''', '''');
    normalized := REPLACE(normalized, '"', '"');
    normalized := REPLACE(normalized, '"', '"');
    normalized := REPLACE(normalized, '–', '-');
    normalized := REPLACE(normalized, '—', '-');

    -- Collapse multiple spaces (use E'' for escape sequences)
    normalized := REGEXP_REPLACE(normalized, E'\\s+', ' ', 'g');

    RETURN TRIM(normalized);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION normalize_team_name_input IS
    'Applies standard team name normalizations (State→St., Saint→St., etc.) centralized from Go/Rust code';


-- Step 2: Update resolve_team_name to use normalization
CREATE OR REPLACE FUNCTION resolve_team_name(input_name TEXT)
RETURNS TEXT AS $$
DECLARE
    v_result TEXT;
    v_normalized TEXT;
BEGIN
    -- Exit early for NULL/empty
    IF input_name IS NULL OR TRIM(input_name) = '' THEN
        RETURN NULL;
    END IF;

    -- STEP 1: Exact match on canonical_name (case-insensitive)
    SELECT t.canonical_name INTO v_result
    FROM teams t
    LEFT JOIN team_ratings tr ON t.id = tr.team_id
    WHERE LOWER(t.canonical_name) = LOWER(TRIM(input_name))
    ORDER BY tr.team_id IS NOT NULL DESC
    LIMIT 1;

    IF v_result IS NOT NULL THEN
        RETURN v_result;
    END IF;

    -- STEP 2: Exact match on alias (case-insensitive)
    SELECT t.canonical_name INTO v_result
    FROM teams t
    JOIN team_aliases ta ON t.id = ta.team_id
    LEFT JOIN team_ratings tr ON t.id = tr.team_id
    WHERE LOWER(ta.alias) = LOWER(TRIM(input_name))
    ORDER BY tr.team_id IS NOT NULL DESC
    LIMIT 1;

    IF v_result IS NOT NULL THEN
        RETURN v_result;
    END IF;

    -- STEP 3: Apply normalization and try again
    v_normalized := normalize_team_name_input(input_name);

    IF v_normalized IS DISTINCT FROM TRIM(input_name) THEN
        -- Try normalized form against canonical_name
        SELECT t.canonical_name INTO v_result
        FROM teams t
        LEFT JOIN team_ratings tr ON t.id = tr.team_id
        WHERE LOWER(t.canonical_name) = LOWER(v_normalized)
        ORDER BY tr.team_id IS NOT NULL DESC
        LIMIT 1;

        IF v_result IS NOT NULL THEN
            RETURN v_result;
        END IF;

        -- Try normalized form against aliases
        SELECT t.canonical_name INTO v_result
        FROM teams t
        JOIN team_aliases ta ON t.id = ta.team_id
        LEFT JOIN team_ratings tr ON t.id = tr.team_id
        WHERE LOWER(ta.alias) = LOWER(v_normalized)
        ORDER BY tr.team_id IS NOT NULL DESC
        LIMIT 1;

        IF v_result IS NOT NULL THEN
            RETURN v_result;
        END IF;
    END IF;

    -- STEP 4: Mascot stripping - remove common mascot suffixes
    v_normalized := REGEXP_REPLACE(TRIM(input_name),
        ' (Wildcats|Bulldogs|Tigers|Eagles|Bears|Lions|Panthers|Hawks|Huskies|Cougars|Cardinals|Blue Devils|Tar Heels|Volunteers|Jayhawks|Spartans|Wolverines|Buckeyes|Boilermakers|Seminoles|Cavaliers|Hoosiers|Badgers|Golden Gophers|Hawkeyes|Cyclones|Mountaineers|Longhorns|Sooners|Cowboys|Aggies|Red Raiders|Horned Frogs|Bruins|Trojans|Sun Devils|Beavers|Ducks|Utes|Buffaloes|Cornhuskers|Razorbacks|Rebels|Commodores|Gamecocks|Gators|Crimson Tide|Fighting Irish|Orange|Demon Deacons|Yellow Jackets|Hokies|Terrapins|Nittany Lions|Scarlet Knights|Golden Flashes|Rockets|Redhawks|Bobcats|Chippewas|Broncos|Thundering Herd|Owls|Billikens|Colonels|Governors|Hatters|Grizzlies|Roadrunners|Matadors|Phoenix|Lumberjacks|Anteaters|Aggies|Mustangs|Mean Green|Roadrunners|Runnin'' Rebels|Wolf Pack|Aztecs|Falcons|Miners|Vandals|Gaels|Zags|Pilots|Waves|Toreros|Lions|Leopards|Raiders|Quakers|Big Red|Big Green|Catamounts|Great Danes|Seawolves|Retrievers|Flames|Monarchs|Dukes|Spiders|Rams|Bonnies|Explorers|Jaspers|Red Foxes|Purple Eagles|Peacocks|Golden Griffins|Stags|Broncs|Musketeers|Bearcats|Flyers|Explorers|Hoyas|Friars|Pirates|Bluejays|Shockers|Braves|Golden Hurricane|Waves|Coyotes|Antelopes|Penguins|Vikings|Crusaders|Hornets|Rattlers|Jaguars|Dolphins)$',
        '', 'i');

    IF v_normalized IS DISTINCT FROM TRIM(input_name) THEN
        -- Apply State→St. normalization to mascot-stripped name too
        v_normalized := normalize_team_name_input(v_normalized);

        SELECT t.canonical_name INTO v_result
        FROM teams t
        LEFT JOIN team_ratings tr ON t.id = tr.team_id
        WHERE LOWER(t.canonical_name) = LOWER(v_normalized)
        ORDER BY tr.team_id IS NOT NULL DESC
        LIMIT 1;

        IF v_result IS NOT NULL THEN
            RETURN v_result;
        END IF;
    END IF;

    -- No match found
    RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION resolve_team_name IS
    'Resolves team name variants to canonical names. Applies centralized normalization (State→St., etc.) and checks aliases. Prefers teams with ratings.';


-- Step 3: Add test cases
DO $$
DECLARE
    test_cases TEXT[][] := ARRAY[
        ARRAY['Florida State', 'Florida St.'],
        ARRAY['Michigan State Spartans', 'Michigan St.'],
        ARRAY['Saint Mary''s', 'St. Mary''s'],
        ARRAY['Northern Iowa', 'N. Iowa'],
        ARRAY['Southern Illinois', 'S. Illinois'],
        ARRAY['Duke Blue Devils', 'Duke'],
        ARRAY['UConn', 'Connecticut'],
        ARRAY['Oregon State Beavers', 'Oregon St.']
    ];
    test_input TEXT;
    expected TEXT;
    actual TEXT;
    i INT;
BEGIN
    FOR i IN 1..array_length(test_cases, 1) LOOP
        test_input := test_cases[i][1];
        expected := test_cases[i][2];
        actual := resolve_team_name(test_input);

        IF actual IS NULL THEN
            RAISE NOTICE 'Test %: resolve_team_name(%) returned NULL (expected: %)', i, test_input, expected;
        ELSIF actual != expected THEN
            RAISE NOTICE 'Test %: resolve_team_name(%) = % (expected: %)', i, test_input, actual, expected;
        ELSE
            RAISE NOTICE 'Test %: ✓ resolve_team_name(%) = %', i, test_input, actual;
        END IF;
    END LOOP;
END $$;


-- Record migration
INSERT INTO schema_migrations (version, name, applied_at)
VALUES (23, '023_centralized_normalization.sql', NOW())
ON CONFLICT (version) DO NOTHING;
