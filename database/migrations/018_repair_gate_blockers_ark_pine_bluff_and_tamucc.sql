-- ═══════════════════════════════════════════════════════════════════════════════
-- MIGRATION 018: Repair today's hard-gate blockers (UAPB, TAMU-CC)
-- ═══════════════════════════════════════════════════════════════════════════════
--
-- Context:
-- The hard gate can fail when a scheduled game points at an unrated duplicate
-- team row whose canonical_name came from the odds feed (includes mascot).
--
-- This migration repairs the two known blockers by:
-- 1) Finding the rated canonical team rows (preferred) via name patterns
-- 2) Adding the odds-style names as aliases to the rated teams (source=the_odds_api)
-- 3) Re-pointing the affected games' team_id to the rated team_id
--
-- Idempotent:
-- - Aliases use ON CONFLICT DO NOTHING
-- - Updates are scoped to specific game_ids and only if the target team exists
--
-- Time zone remains CST: 'America/Chicago'
--

DO $$
DECLARE
    v_uapb_rated UUID;
    v_tamucc_rated UUID;
BEGIN
    -- -------------------------------------------------------------------------
    -- Arkansas-Pine Bluff (UAPB)
    -- -------------------------------------------------------------------------
    SELECT t.id
    INTO v_uapb_rated
    FROM teams t
    WHERE EXISTS (SELECT 1 FROM team_ratings tr WHERE tr.team_id = t.id)
      AND lower(t.canonical_name) LIKE '%pine%bluff%'
    ORDER BY t.canonical_name
    LIMIT 1;

    IF v_uapb_rated IS NULL THEN
        RAISE NOTICE 'Migration 018: could not find rated team for Pine Bluff (no action).';
    ELSE
        INSERT INTO team_aliases (team_id, alias, source, confidence)
        VALUES (v_uapb_rated, 'Arkansas-Pine Bluff Golden Lions', 'the_odds_api', 1.0)
        ON CONFLICT (alias, source) DO NOTHING;

        -- Re-point the specific blocked game (home team)
        UPDATE games g
        SET home_team_id = v_uapb_rated
        WHERE g.id = 'a11fff73-fde7-4f06-bed3-5eac4cccb5d1'::uuid;
    END IF;

    -- -------------------------------------------------------------------------
    -- Texas A&M-CC (TAMU-CC / Corpus Christi)
    -- -------------------------------------------------------------------------
    SELECT t.id
    INTO v_tamucc_rated
    FROM teams t
    WHERE EXISTS (SELECT 1 FROM team_ratings tr WHERE tr.team_id = t.id)
      AND lower(t.canonical_name) LIKE '%a&m%'
      AND lower(t.canonical_name) LIKE '%corpus%'
    ORDER BY t.canonical_name
    LIMIT 1;

    IF v_tamucc_rated IS NULL THEN
        RAISE NOTICE 'Migration 018: could not find rated team for TAMU-CC/Corpus Christi (no action).';
    ELSE
        INSERT INTO team_aliases (team_id, alias, source, confidence)
        VALUES (v_tamucc_rated, 'Texas A&M-CC Islanders', 'the_odds_api', 1.0)
        ON CONFLICT (alias, source) DO NOTHING;

        -- Re-point the specific blocked game (away team)
        UPDATE games g
        SET away_team_id = v_tamucc_rated
        WHERE g.id = '67b015fd-add9-440c-903b-c17fffe81391'::uuid;
    END IF;
END $$;

