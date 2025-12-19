-- Team Matching & Home/Away Validation System
-- Ensures absolute accuracy across all ingestion sources

-- ═══════════════════════════════════════════════════════════════════════════════
-- VALIDATION FUNCTIONS
-- ═══════════════════════════════════════════════════════════════════════════════

-- Validate that a team name resolves correctly
CREATE OR REPLACE FUNCTION validate_team_name(input_name TEXT) 
RETURNS TABLE(
    canonical_name TEXT,
    has_ratings BOOLEAN,
    confidence TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        t.canonical_name,
        (tr.team_id IS NOT NULL) as has_ratings,
        CASE 
            WHEN tr.team_id IS NOT NULL THEN 'HIGH - Has Barttorvik ratings'
            WHEN ta.team_id IS NOT NULL THEN 'MEDIUM - Alias found but no ratings'
            WHEN t.id IS NOT NULL THEN 'LOW - Team exists but no alias/ratings'
            ELSE 'NONE - Team not found'
        END as confidence
    FROM teams t
    LEFT JOIN team_aliases ta ON t.id = ta.team_id AND LOWER(ta.alias) = LOWER(input_name)
    LEFT JOIN team_ratings tr ON t.id = tr.team_id
    WHERE LOWER(t.canonical_name) = LOWER(input_name)
       OR LOWER(ta.alias) = LOWER(input_name)
    ORDER BY tr.team_id IS NOT NULL DESC, t.canonical_name
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Validate home/away assignment consistency
-- Checks that both teams resolve correctly and are different
CREATE OR REPLACE FUNCTION validate_game_teams(
    p_home_team_name TEXT,
    p_away_team_name TEXT
) RETURNS TABLE(
    home_canonical TEXT,
    away_canonical TEXT,
    home_has_ratings BOOLEAN,
    away_has_ratings BOOLEAN,
    is_valid BOOLEAN,
    validation_errors TEXT[]
) AS $$
DECLARE
    v_home_canonical TEXT;
    v_away_canonical TEXT;
    v_home_has_ratings BOOLEAN;
    v_away_has_ratings BOOLEAN;
    v_errors TEXT[] := ARRAY[]::TEXT[];
BEGIN
    -- Resolve home team
    SELECT canonical_name, (tr.team_id IS NOT NULL)
    INTO v_home_canonical, v_home_has_ratings
    FROM teams t
    LEFT JOIN team_aliases ta ON t.id = ta.team_id AND LOWER(ta.alias) = LOWER(p_home_team_name)
    LEFT JOIN team_ratings tr ON t.id = tr.team_id
    WHERE LOWER(t.canonical_name) = LOWER(p_home_team_name)
       OR LOWER(ta.alias) = LOWER(p_home_team_name)
    ORDER BY tr.team_id IS NOT NULL DESC, t.canonical_name
    LIMIT 1;
    
    -- Resolve away team
    SELECT canonical_name, (tr.team_id IS NOT NULL)
    INTO v_away_canonical, v_away_has_ratings
    FROM teams t
    LEFT JOIN team_aliases ta ON t.id = ta.team_id AND LOWER(ta.alias) = LOWER(p_away_team_name)
    LEFT JOIN team_ratings tr ON t.id = tr.team_id
    WHERE LOWER(t.canonical_name) = LOWER(p_away_team_name)
       OR LOWER(ta.alias) = LOWER(p_away_team_name)
    ORDER BY tr.team_id IS NOT NULL DESC, t.canonical_name
    LIMIT 1;
    
    -- Validation checks
    IF v_home_canonical IS NULL THEN
        v_errors := array_append(v_errors, 'Home team "' || p_home_team_name || '" not found');
    END IF;
    
    IF v_away_canonical IS NULL THEN
        v_errors := array_append(v_errors, 'Away team "' || p_away_team_name || '" not found');
    END IF;
    
    IF v_home_canonical IS NOT NULL AND v_away_canonical IS NOT NULL AND v_home_canonical = v_away_canonical THEN
        v_errors := array_append(v_errors, 'Home and away teams are the same: ' || v_home_canonical);
    END IF;
    
    IF NOT v_home_has_ratings THEN
        v_errors := array_append(v_errors, 'Home team "' || COALESCE(v_home_canonical, p_home_team_name) || '" has no ratings');
    END IF;
    
    IF NOT v_away_has_ratings THEN
        v_errors := array_append(v_errors, 'Away team "' || COALESCE(v_away_canonical, p_away_team_name) || '" has no ratings');
    END IF;
    
    RETURN QUERY SELECT 
        v_home_canonical,
        v_away_canonical,
        COALESCE(v_home_has_ratings, FALSE),
        COALESCE(v_away_has_ratings, FALSE),
        (array_length(v_errors, 1) IS NULL),
        v_errors;
END;
$$ LANGUAGE plpgsql;

-- ═══════════════════════════════════════════════════════════════════════════════
-- AUDIT TABLE FOR TEAM MATCHING
-- ═══════════════════════════════════════════════════════════════════════════════

-- Track all team name resolution attempts for debugging
CREATE TABLE IF NOT EXISTS team_resolution_audit (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    input_name      TEXT NOT NULL,
    resolved_name   TEXT,
    source          TEXT NOT NULL,  -- 'the_odds_api', 'barttorvik', etc.
    context         TEXT,           -- 'home_team', 'away_team', etc.
    has_ratings     BOOLEAN,
    confidence      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
    -- Note: Allow multiple entries for same input (track resolution over time)
    -- No unique constraint - we want to track all resolution attempts
);

CREATE INDEX idx_team_resolution_audit_input ON team_resolution_audit(LOWER(input_name));
CREATE INDEX idx_team_resolution_audit_source ON team_resolution_audit(source);
CREATE INDEX idx_team_resolution_audit_created ON team_resolution_audit(created_at DESC);

-- ═══════════════════════════════════════════════════════════════════════════════
-- GAME VALIDATION TRIGGER
-- ═══════════════════════════════════════════════════════════════════════════════

-- Log validation warnings (but don't block inserts)
CREATE OR REPLACE FUNCTION log_game_validation()
RETURNS TRIGGER AS $$
DECLARE
    v_validation RECORD;
BEGIN
    -- Get team names for validation
    SELECT * INTO v_validation
    FROM validate_game_teams(
        (SELECT canonical_name FROM teams WHERE id = NEW.home_team_id),
        (SELECT canonical_name FROM teams WHERE id = NEW.away_team_id)
    );
    
    -- Log if validation fails
    IF NOT v_validation.is_valid THEN
        RAISE WARNING 'Game validation failed for game %: %', NEW.id, array_to_string(v_validation.validation_errors, '; ');
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_validate_game_teams
    AFTER INSERT OR UPDATE ON games
    FOR EACH ROW
    EXECUTE FUNCTION log_game_validation();

-- ═══════════════════════════════════════════════════════════════════════════════
-- HELPER VIEWS
-- ═══════════════════════════════════════════════════════════════════════════════

-- View of games with validation status
CREATE OR REPLACE VIEW games_validation_status AS
SELECT 
    g.id,
    g.external_id,
    ht.canonical_name as home_team,
    at.canonical_name as away_team,
    g.commence_time,
    g.status,
    (SELECT COUNT(*) > 0 FROM team_ratings WHERE team_id = g.home_team_id) as home_has_ratings,
    (SELECT COUNT(*) > 0 FROM team_ratings WHERE team_id = g.away_team_id) as away_has_ratings,
    (SELECT COUNT(*) > 0 FROM team_ratings WHERE team_id = g.home_team_id) 
        AND (SELECT COUNT(*) > 0 FROM team_ratings WHERE team_id = g.away_team_id) as both_have_ratings
FROM games g
JOIN teams ht ON g.home_team_id = ht.id
JOIN teams at ON g.away_team_id = at.id;

COMMENT ON FUNCTION validate_team_name IS 'Validates team name resolution and returns confidence level';
COMMENT ON FUNCTION validate_game_teams IS 'Validates home/away team assignment and returns validation errors';
COMMENT ON TABLE team_resolution_audit IS 'Audit log of all team name resolution attempts for debugging';
