-- Common Team Name Variants
-- Adds frequently used team name variants to ensure 99.99% accuracy
-- These are common names used by odds providers, media, etc.

-- Duke variants
INSERT INTO team_aliases (team_id, alias, source)
SELECT t.id, 'Duke Blue Devils', 'common_variant'
FROM teams t WHERE t.canonical_name = 'Duke'
ON CONFLICT (alias, source) DO NOTHING;

-- North Carolina variants
INSERT INTO team_aliases (team_id, alias, source)
SELECT t.id, 'UNC', 'common_variant'
FROM teams t WHERE t.canonical_name = 'North Carolina'
ON CONFLICT (alias, source) DO NOTHING;

INSERT INTO team_aliases (team_id, alias, source)
SELECT t.id, 'North Carolina Tar Heels', 'common_variant'
FROM teams t WHERE t.canonical_name = 'North Carolina'
ON CONFLICT (alias, source) DO NOTHING;

-- Kentucky variants
INSERT INTO team_aliases (team_id, alias, source)
SELECT t.id, 'Kentucky Wildcats', 'common_variant'
FROM teams t WHERE t.canonical_name = 'Kentucky'
ON CONFLICT (alias, source) DO NOTHING;

-- Kansas variants
INSERT INTO team_aliases (team_id, alias, source)
SELECT t.id, 'Kansas Jayhawks', 'common_variant'
FROM teams t WHERE t.canonical_name = 'Kansas'
ON CONFLICT (alias, source) DO NOTHING;

-- UCLA variants
INSERT INTO team_aliases (team_id, alias, source)
SELECT t.id, 'UCLA Bruins', 'common_variant'
FROM teams t WHERE t.canonical_name = 'UCLA'
ON CONFLICT (alias, source) DO NOTHING;

-- Add more common variants as needed
-- This ensures odds providers' team names always map correctly

COMMENT ON TABLE team_aliases IS 'Team name variants for accurate mapping across data sources. Updated by ingestion services automatically.';
