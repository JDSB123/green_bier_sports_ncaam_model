-- ═══════════════════════════════════════════════════════════════════════════════
-- MIGRATION 017: Fix validate_todays_team_matching() ambiguity bug
-- ═══════════════════════════════════════════════════════════════════════════════
--
-- Purpose:
-- In PL/pgSQL, RETURNS TABLE column names are visible as variables inside the
-- function body. The original implementation used:
--   SELECT * FROM home_check WHERE blocker_reason IS NOT NULL
-- which becomes ambiguous between the output variable and the CTE column.
--
-- Fix:
-- Qualify the CTE columns via table aliases (hc.blocker_reason / ac.blocker_reason).
--
-- Time zone remains CST: 'America/Chicago'
--

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
    SELECT * FROM home_check hc WHERE hc.blocker_reason IS NOT NULL
    UNION ALL
    SELECT * FROM away_check ac WHERE ac.blocker_reason IS NOT NULL
    ORDER BY commence_time, team_position;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION validate_todays_team_matching IS
    'Pre-flight validation: Returns any teams that would block predictions for target date (CST). Fixed ambiguity by qualifying blocker_reason.';

