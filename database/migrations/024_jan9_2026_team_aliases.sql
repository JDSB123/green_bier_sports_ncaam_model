-- ═══════════════════════════════════════════════════════════════════════════════
-- MIGRATION 024: Add missing team aliases from Jan 9, 2026 slate
-- ═══════════════════════════════════════════════════════════════════════════════
--
-- Purpose: Add 7 new team aliases discovered during team resolution testing
-- for the Jan 9, 2026 game slate. These aliases are for Wisconsin system schools
-- and state university abbreviations.
--
-- Source: The Odds API returns shortened names like "Wisc Green Bay" that need
-- to map to the canonical Barttorvik names.
--
-- ═══════════════════════════════════════════════════════════════════════════════

-- Wisconsin - Green Bay aliases
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'wisc green bay', 'the_odds_api', 1.0
FROM teams t WHERE t.canonical_name = 'Green Bay'
ON CONFLICT (alias, source) DO NOTHING;

INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'wisconsin green bay', 'the_odds_api', 1.0
FROM teams t WHERE t.canonical_name = 'Green Bay'
ON CONFLICT (alias, source) DO NOTHING;

-- Wisconsin - Milwaukee aliases
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'wisc milwaukee', 'the_odds_api', 1.0
FROM teams t WHERE t.canonical_name = 'Milwaukee'
ON CONFLICT (alias, source) DO NOTHING;

INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'wisconsin milwaukee', 'the_odds_api', 1.0
FROM teams t WHERE t.canonical_name = 'Milwaukee'
ON CONFLICT (alias, source) DO NOTHING;

-- Cleveland State alias
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'cleveland st', 'the_odds_api', 1.0
FROM teams t WHERE t.canonical_name = 'Cleveland St.'
ON CONFLICT (alias, source) DO NOTHING;

-- Wright State alias
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'wright st', 'the_odds_api', 1.0
FROM teams t WHERE t.canonical_name = 'Wright St.'
ON CONFLICT (alias, source) DO NOTHING;

-- Colorado State alias  
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'colorado st', 'the_odds_api', 1.0
FROM teams t WHERE t.canonical_name = 'Colorado St.'
ON CONFLICT (alias, source) DO NOTHING;

