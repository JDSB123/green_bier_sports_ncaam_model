-- ═══════════════════════════════════════════════════════════════════════════════
-- MIGRATION 019: Make hard-gate match_rate slot-based (games*2)
-- ═══════════════════════════════════════════════════════════════════════════════
--
-- Problem:
-- check_100_percent_match_gate() computed teams_with_ratings as DISTINCT teams,
-- while total_teams is team slots (games * 2). This can show <100% even when
-- every scheduled team slot has ratings (e.g., a team plays twice).
--
-- Fix:
-- Compute teams_with_ratings as *slot-based*:
--   rated_slots = (home slots with ratings) + (away slots with ratings)
-- Then:
--   match_rate = rated_slots / total_slots * 100
--
-- Gate correctness still relies on blockers from validate_todays_team_matching().
-- Time zone remains CST: 'America/Chicago'
--

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
    -- Count team slots from today's scheduled games (CST)
    SELECT
        COUNT(*) * 2,  -- team slots (home + away)
        COUNT(g.home_team_id) + COUNT(g.away_team_id),
        -- rated slots (home slots + away slots)
        SUM(CASE WHEN EXISTS(SELECT 1 FROM team_ratings tr WHERE tr.team_id = g.home_team_id) THEN 1 ELSE 0 END)
        +
        SUM(CASE WHEN EXISTS(SELECT 1 FROM team_ratings tr WHERE tr.team_id = g.away_team_id) THEN 1 ELSE 0 END)
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
    'Hard gate check (CST): gate_passed is based on blockers; teams_with_ratings/match_rate are slot-based (games*2).';

