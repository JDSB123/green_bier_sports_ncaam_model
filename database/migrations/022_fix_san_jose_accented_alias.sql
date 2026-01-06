-- Fix: Add missing accented variant for San Jose State
-- The Odds API sometimes returns "San José St Spartans" (with accented é)
-- This migration adds that variant to ensure 100% team matching

INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'San José St Spartans', 'the_odds_api', 1.0
FROM teams t
WHERE t.canonical_name = 'San Jose St.'
ON CONFLICT (alias, source) DO NOTHING;

-- Also add common variations that might appear
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    ('San José State Spartans'),
    ('San Jose St Spartans'),
    ('SJSU Spartans')
) AS a(alias)
WHERE t.canonical_name = 'San Jose St.'
ON CONFLICT (alias, source) DO NOTHING;
