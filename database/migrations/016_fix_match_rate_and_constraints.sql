-- ═══════════════════════════════════════════════════════════════════════════════
-- MIGRATION 016: Fix hard gate match_rate and add data hygiene constraints
-- ═══════════════════════════════════════════════════════════════════════════════
--
-- Purpose:
-- 1) Correct match_rate calculation in check_100_percent_match_gate()
--    - v_total already counts TEAMS (games * 2). Do NOT multiply by 2 again.
-- 2) Add a guardrail constraint to ensure home_team_id != away_team_id
--
-- Notes:
-- - Time zone remains CST ('America/Chicago') throughout, unchanged.
-- - Function is replaced idempotently via CREATE OR REPLACE.
--

-- 1) Fix match_rate calculation
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
    -- Count teams from today's scheduled games (CST)
    SELECT
        COUNT(*) * 2,  -- home + away (TEAMS)
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
        CASE WHEN v_total > 0 THEN (v_with_ratings::NUMERIC / v_total * 100) ELSE 0 END as match_rate,
        v_blockers as blockers;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION check_100_percent_match_gate IS
    'Hard gate check: Returns gate_passed=TRUE only if ALL teams for target date are resolved with ratings. match_rate computed as teams_with_ratings / total_teams (CST).';


-- 2) Data hygiene: home_team_id must differ from away_team_id
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_games_home_neq_away'
          AND conrelid = 'games'::regclass
    ) THEN
        ALTER TABLE games
        ADD CONSTRAINT chk_games_home_neq_away
        CHECK (
            home_team_id IS NULL
            OR away_team_id IS NULL
            OR home_team_id <> away_team_id
        );
    END IF;
END$$;

-- End of migration 016

