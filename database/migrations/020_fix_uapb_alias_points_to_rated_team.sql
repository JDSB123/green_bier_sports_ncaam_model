-- ═══════════════════════════════════════════════════════════════════════════════
-- MIGRATION 020: Fix UAPB odds alias to point at rated canonical team
-- ═══════════════════════════════════════════════════════════════════════════════
--
-- Problem:
-- The Odds API name "Arkansas-Pine Bluff Golden Lions" exists in team_aliases
-- (source=the_odds_api) but was attached to an unrated duplicate team row with
-- canonical_name equal to the full odds string.
--
-- Because resolve_team_name() prefers rated teams only among candidates that
-- match (canonical OR alias), an alias bound to an unrated duplicate can cause
-- odds ingestion to keep resolving to that unrated team_id, failing the hard gate.
--
-- Fix:
-- 1) Identify the rated canonical team row for UAPB: canonical_name contains
--    "arkansas" + "pine" + "bluff" and has ratings
-- 2) Point the existing the_odds_api alias row at that rated team_id
-- 3) Re-point any scheduled games that reference the unrated duplicate team_id
--
-- Idempotent and safe:
-- - UPDATEs are no-ops if rows already correct.
-- - If the rated team cannot be found, the migration does nothing.
--

DO $$
DECLARE
    v_rated UUID;
    v_unrated UUID;
BEGIN
    -- Find rated UAPB canonical team
    SELECT t.id
    INTO v_rated
    FROM teams t
    WHERE EXISTS (SELECT 1 FROM team_ratings tr WHERE tr.team_id = t.id)
      AND lower(t.canonical_name) LIKE '%arkansas%'
      AND lower(t.canonical_name) LIKE '%pine%'
      AND lower(t.canonical_name) LIKE '%bluff%'
    ORDER BY t.canonical_name
    LIMIT 1;

    IF v_rated IS NULL THEN
        RAISE NOTICE 'Migration 020: rated UAPB team not found (no action).';
        RETURN;
    END IF;

    -- Find the unrated duplicate (canonical equals odds string)
    SELECT t.id
    INTO v_unrated
    FROM teams t
    WHERE t.canonical_name = 'Arkansas-Pine Bluff Golden Lions'
    LIMIT 1;

    -- Ensure the_odds_api alias row points to the rated team
    UPDATE team_aliases
    SET team_id = v_rated,
        confidence = GREATEST(COALESCE(confidence, 1.0), 1.0)
    WHERE alias = 'Arkansas-Pine Bluff Golden Lions'
      AND source = 'the_odds_api';

    -- If we have an unrated duplicate team row, re-point today's scheduled games
    IF v_unrated IS NOT NULL AND v_unrated <> v_rated THEN
        UPDATE games g
        SET home_team_id = v_rated
        WHERE g.status = 'scheduled'
          AND g.home_team_id = v_unrated;

        UPDATE games g
        SET away_team_id = v_rated
        WHERE g.status = 'scheduled'
          AND g.away_team_id = v_unrated;
    END IF;
END $$;

