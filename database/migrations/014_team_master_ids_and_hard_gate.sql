-- ═══════════════════════════════════════════════════════════════════════════════
-- MIGRATION 014: Team Master IDs and Hard Matching Gate
-- ═══════════════════════════════════════════════════════════════════════════════
--
-- Purpose: Add unique external IDs and location disambiguators to prevent
-- incorrect team matching (e.g., Tennessee vs Tennessee State).
--
-- Best Practices Implemented:
--   1. Unique external IDs from authoritative sources (NCAA, ESPN, Sports-Reference)
--   2. Location disambiguators (city, state) for teams with similar names
--   3. Conference as mandatory tie-breaker
--   4. Hard gate requiring 100% match for today's games before picks
--
-- ═══════════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────────────
-- STEP 1: Add external IDs and location columns to teams table
-- ─────────────────────────────────────────────────────────────────────────────────

ALTER TABLE teams ADD COLUMN IF NOT EXISTS ncaa_id INTEGER UNIQUE;
ALTER TABLE teams ADD COLUMN IF NOT EXISTS espn_id INTEGER UNIQUE;
ALTER TABLE teams ADD COLUMN IF NOT EXISTS sports_ref_id TEXT UNIQUE;
ALTER TABLE teams ADD COLUMN IF NOT EXISTS city TEXT;
ALTER TABLE teams ADD COLUMN IF NOT EXISTS state TEXT;

-- Add comments explaining the columns
COMMENT ON COLUMN teams.ncaa_id IS 'Official NCAA team ID from ncaa.com';
COMMENT ON COLUMN teams.espn_id IS 'ESPN team ID from espn.com/mens-college-basketball';
COMMENT ON COLUMN teams.sports_ref_id IS 'Sports-Reference school ID (e.g., "tennessee")';
COMMENT ON COLUMN teams.city IS 'City location for disambiguation (e.g., "Knoxville" vs "Nashville")';
COMMENT ON COLUMN teams.state IS 'State abbreviation for disambiguation';

-- Create indexes for fast lookups by external IDs
CREATE INDEX IF NOT EXISTS idx_teams_ncaa_id ON teams(ncaa_id);
CREATE INDEX IF NOT EXISTS idx_teams_espn_id ON teams(espn_id);
CREATE INDEX IF NOT EXISTS idx_teams_sports_ref_id ON teams(sports_ref_id);
CREATE INDEX IF NOT EXISTS idx_teams_state ON teams(state);

-- ─────────────────────────────────────────────────────────────────────────────────
-- STEP 2: Populate Tennessee-related teams with disambiguators (critical examples)
-- ─────────────────────────────────────────────────────────────────────────────────

-- Tennessee (SEC) - The Vols in Knoxville
UPDATE teams SET
    city = 'Knoxville',
    state = 'TN',
    espn_id = 2633,
    sports_ref_id = 'tennessee'
WHERE canonical_name = 'Tennessee';

-- Tennessee State (OVC) - Tigers in Nashville
UPDATE teams SET
    city = 'Nashville',
    state = 'TN',
    espn_id = 2634,
    sports_ref_id = 'tennessee-state'
WHERE canonical_name = 'Tennessee St.';

-- Tennessee Tech (OVC) - Golden Eagles in Cookeville
UPDATE teams SET
    city = 'Cookeville',
    state = 'TN',
    espn_id = 2635,
    sports_ref_id = 'tennessee-tech'
WHERE canonical_name = 'Tennessee Tech';

-- East Tennessee State (SoCon) - Buccaneers in Johnson City
UPDATE teams SET
    city = 'Johnson City',
    state = 'TN',
    espn_id = 151,
    sports_ref_id = 'east-tennessee-state'
WHERE canonical_name = 'ETSU';

-- UT Martin (OVC) - Skyhawks in Martin
UPDATE teams SET
    city = 'Martin',
    state = 'TN',
    espn_id = 2630,
    sports_ref_id = 'tennessee-martin'
WHERE canonical_name = 'UT Martin';

-- Middle Tennessee (CUSA) - Blue Raiders in Murfreesboro
UPDATE teams SET
    city = 'Murfreesboro',
    state = 'TN',
    espn_id = 2393,
    sports_ref_id = 'middle-tennessee-state'
WHERE canonical_name = 'Middle Tennessee';

-- ─────────────────────────────────────────────────────────────────────────────────
-- STEP 3: Populate other commonly confused teams
-- ─────────────────────────────────────────────────────────────────────────────────

-- Miami variants
UPDATE teams SET city = 'Coral Gables', state = 'FL', espn_id = 2390
WHERE canonical_name = 'Miami FL';

UPDATE teams SET city = 'Oxford', state = 'OH', espn_id = 193
WHERE canonical_name = 'Miami OH';

-- USC variants
UPDATE teams SET city = 'Los Angeles', state = 'CA', espn_id = 30
WHERE canonical_name = 'USC';

UPDATE teams SET city = 'Columbia', state = 'SC', espn_id = 2579
WHERE canonical_name = 'South Carolina';

-- Washington variants
UPDATE teams SET city = 'Seattle', state = 'WA', espn_id = 264
WHERE canonical_name = 'Washington';

UPDATE teams SET city = 'Pullman', state = 'WA', espn_id = 265
WHERE canonical_name = 'Washington St.';

-- Florida variants
UPDATE teams SET city = 'Gainesville', state = 'FL', espn_id = 57
WHERE canonical_name = 'Florida';

UPDATE teams SET city = 'Tallahassee', state = 'FL', espn_id = 52
WHERE canonical_name = 'Florida St.';

-- ─────────────────────────────────────────────────────────────────────────────────
-- STEP 4: Create pre-flight validation function for today's games
-- ─────────────────────────────────────────────────────────────────────────────────

-- Function to validate ALL teams for today's games are resolved
-- Returns a table of any unresolved teams that would block predictions
CREATE OR REPLACE FUNCTION validate_todays_team_matching(target_date DATE DEFAULT CURRENT_DATE)
RETURNS TABLE (
    game_id UUID,
    commence_time TIMESTAMPTZ,
    team_position TEXT,
    raw_team_name TEXT,
    resolved_canonical TEXT,
    has_ratings BOOLEAN,
    blocker_reason TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH todays_games AS (
        SELECT
            g.id,
            g.commence_time,
            g.home_team_id,
            g.away_team_id,
            ht.canonical_name as home_canonical,
            at.canonical_name as away_canonical
        FROM games g
        LEFT JOIN teams ht ON g.home_team_id = ht.id
        LEFT JOIN teams at ON g.away_team_id = at.id
        WHERE DATE(g.commence_time AT TIME ZONE 'America/Chicago') = target_date
          AND g.status = 'scheduled'
    ),
    home_check AS (
        SELECT
            tg.id as game_id,
            tg.commence_time,
            'home' as team_position,
            tg.home_canonical as raw_team_name,
            tg.home_canonical as resolved_canonical,
            EXISTS(SELECT 1 FROM team_ratings tr WHERE tr.team_id = tg.home_team_id) as has_ratings,
            CASE
                WHEN tg.home_team_id IS NULL THEN 'Team not resolved to canonical'
                WHEN NOT EXISTS(SELECT 1 FROM team_ratings tr WHERE tr.team_id = tg.home_team_id)
                    THEN 'No ratings data for team'
                ELSE NULL
            END as blocker_reason
        FROM todays_games tg
    ),
    away_check AS (
        SELECT
            tg.id as game_id,
            tg.commence_time,
            'away' as team_position,
            tg.away_canonical as raw_team_name,
            tg.away_canonical as resolved_canonical,
            EXISTS(SELECT 1 FROM team_ratings tr WHERE tr.team_id = tg.away_team_id) as has_ratings,
            CASE
                WHEN tg.away_team_id IS NULL THEN 'Team not resolved to canonical'
                WHEN NOT EXISTS(SELECT 1 FROM team_ratings tr WHERE tr.team_id = tg.away_team_id)
                    THEN 'No ratings data for team'
                ELSE NULL
            END as blocker_reason
        FROM todays_games tg
    )
    SELECT * FROM home_check WHERE blocker_reason IS NOT NULL
    UNION ALL
    SELECT * FROM away_check WHERE blocker_reason IS NOT NULL
    ORDER BY commence_time, team_position;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION validate_todays_team_matching IS
    'Pre-flight validation: Returns any teams that would block predictions for target date. Empty result = 100% ready.';

-- ─────────────────────────────────────────────────────────────────────────────────
-- STEP 5: Create hard gate check function (returns TRUE only if 100% ready)
-- ─────────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION check_100_percent_match_gate(target_date DATE DEFAULT CURRENT_DATE)
RETURNS TABLE (
    gate_passed BOOLEAN,
    total_teams INTEGER,
    resolved_teams INTEGER,
    teams_with_ratings INTEGER,
    match_rate NUMERIC,
    blockers JSONB
) AS $$
DECLARE
    v_total INTEGER;
    v_resolved INTEGER;
    v_with_ratings INTEGER;
    v_blockers JSONB;
BEGIN
    -- Count teams from today's games
    SELECT
        COUNT(*) * 2,  -- home + away
        COUNT(g.home_team_id) + COUNT(g.away_team_id),
        (SELECT COUNT(*) FROM (
            SELECT DISTINCT home_team_id as tid FROM games
            WHERE DATE(commence_time AT TIME ZONE 'America/Chicago') = target_date AND status = 'scheduled'
            UNION
            SELECT DISTINCT away_team_id FROM games
            WHERE DATE(commence_time AT TIME ZONE 'America/Chicago') = target_date AND status = 'scheduled'
        ) t WHERE EXISTS(SELECT 1 FROM team_ratings tr WHERE tr.team_id = t.tid))
    INTO v_total, v_resolved, v_with_ratings
    FROM games g
    WHERE DATE(g.commence_time AT TIME ZONE 'America/Chicago') = target_date
      AND g.status = 'scheduled';

    -- Get any blockers
    SELECT COALESCE(jsonb_agg(jsonb_build_object(
        'game_id', b.game_id,
        'team_position', b.team_position,
        'team_name', b.raw_team_name,
        'reason', b.blocker_reason
    )), '[]'::jsonb)
    INTO v_blockers
    FROM validate_todays_team_matching(target_date) b;

    RETURN QUERY SELECT
        (v_blockers = '[]'::jsonb) as gate_passed,
        v_total as total_teams,
        v_resolved as resolved_teams,
        v_with_ratings as teams_with_ratings,
        CASE WHEN v_total > 0 THEN (v_with_ratings::NUMERIC / v_total * 2 * 100) ELSE 0 END as match_rate,
        v_blockers as blockers;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION check_100_percent_match_gate IS
    'Hard gate check: Returns gate_passed=TRUE only if ALL teams for target date are resolved with ratings. blockers contains any issues.';

-- ─────────────────────────────────────────────────────────────────────────────────
-- STEP 6: Update resolve_team_name to prefer matches with external IDs
-- ─────────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION resolve_team_name_v2(
    input_name TEXT,
    hint_conference TEXT DEFAULT NULL,
    hint_city TEXT DEFAULT NULL,
    hint_state TEXT DEFAULT NULL
)
RETURNS TEXT AS $$
DECLARE
    v_result TEXT;
    v_normalized TEXT;
BEGIN
    -- Return NULL for empty input
    IF input_name IS NULL OR TRIM(input_name) = '' THEN
        RETURN NULL;
    END IF;

    v_normalized := LOWER(TRIM(input_name));

    -- STEP 1: Exact match on canonical_name with disambiguators
    IF hint_conference IS NOT NULL OR hint_city IS NOT NULL OR hint_state IS NOT NULL THEN
        SELECT t.canonical_name INTO v_result
        FROM teams t
        LEFT JOIN team_ratings tr ON t.id = tr.team_id
        WHERE LOWER(t.canonical_name) = v_normalized
          AND (hint_conference IS NULL OR LOWER(t.conference) = LOWER(hint_conference))
          AND (hint_city IS NULL OR LOWER(t.city) = LOWER(hint_city))
          AND (hint_state IS NULL OR LOWER(t.state) = LOWER(hint_state))
        ORDER BY tr.team_id IS NOT NULL DESC
        LIMIT 1;

        IF v_result IS NOT NULL THEN
            RETURN v_result;
        END IF;
    END IF;

    -- STEP 2: Fall back to original resolve_team_name (no fuzzy!)
    RETURN resolve_team_name(input_name);
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION resolve_team_name_v2 IS
    'Enhanced team resolution with optional conference/city/state hints for disambiguation. Use hints to distinguish Tennessee (SEC, Knoxville) from Tennessee State (OVC, Nashville).';

-- ─────────────────────────────────────────────────────────────────────────────────
-- STEP 7: Log migration completion
-- ─────────────────────────────────────────────────────────────────────────────────

DO $$
DECLARE
    teams_with_espn INTEGER;
    teams_with_city INTEGER;
BEGIN
    SELECT COUNT(*) INTO teams_with_espn FROM teams WHERE espn_id IS NOT NULL;
    SELECT COUNT(*) INTO teams_with_city FROM teams WHERE city IS NOT NULL;
    RAISE NOTICE 'Migration 014 complete: % teams with ESPN IDs, % teams with city disambiguation',
        teams_with_espn, teams_with_city;
END;
$$;
