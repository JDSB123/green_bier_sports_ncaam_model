-- ═══════════════════════════════════════════════════════════════════════════════
-- MIGRATION 015: Import Standardized Team Mappings (Template)
-- ═══════════════════════════════════════════════════════════════════════════════
--
-- Purpose: Template for importing standardized team name mappings from R packages
-- (ncaahoopR, hoopR, toRvik) into the team_aliases table.
--
-- This migration is a TEMPLATE. To use it:
--   1. Extract data from R packages (see docs/STANDARDIZED_TEAM_MAPPINGS.md)
--   2. Run import_standardized_team_mappings.py script to import mappings
--   3. Or manually add mappings below using the INSERT pattern
--
-- Sources:
--   - ncaahoopR: Maps variants across NCAA, ESPN, WarrenNolan, Trank (Bart Torvik), 247Sports
--   - hoopR: Maps ESPN and KenPom variants
--   - toRvik: Bart Torvik native formats
--
-- ═══════════════════════════════════════════════════════════════════════════════

-- Example: Import KenPom mappings from hoopR
-- Replace with actual mappings extracted from R packages

-- INSERT INTO team_aliases (team_id, alias, source, confidence)
-- SELECT t.id, a.alias, 'hoopr_kenpom', 1.0
-- FROM teams t
-- CROSS JOIN LATERAL (VALUES
--     ('Duke', 'Duke (KenPom format)'),
--     ('North Carolina', 'UNC (KenPom format)')
--     -- Add more mappings here
-- ) AS a(canonical, alias)
-- WHERE t.canonical_name = a.canonical
-- ON CONFLICT (alias, source) DO NOTHING;

-- Example: Import ESPN mappings from ncaahoopR
-- INSERT INTO team_aliases (team_id, alias, source, confidence)
-- SELECT t.id, a.alias, 'ncaahoopr_espn', 1.0
-- FROM teams t
-- CROSS JOIN LATERAL (VALUES
--     ('Duke', 'Duke Blue Devils (ESPN)'),
--     ('North Carolina', 'North Carolina Tar Heels (ESPN)')
--     -- Add more mappings here
-- ) AS a(canonical, alias)
-- WHERE t.canonical_name = a.canonical
-- ON CONFLICT (alias, source) DO NOTHING;

-- Example: Import WarrenNolan mappings from ncaahoopR
-- INSERT INTO team_aliases (team_id, alias, source, confidence)
-- SELECT t.id, a.alias, 'ncaahoopr_warren_nolan', 1.0
-- FROM teams t
-- CROSS JOIN LATERAL (VALUES
--     ('Duke', 'Duke (WarrenNolan format)')
--     -- Add more mappings here
-- ) AS a(canonical, alias)
-- WHERE t.canonical_name = a.canonical
-- ON CONFLICT (alias, source) DO NOTHING;

-- Log migration completion
DO $$
DECLARE
    ncaahoopr_count INTEGER;
    hoopr_count INTEGER;
    torvik_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO ncaahoopr_count
    FROM team_aliases
    WHERE source LIKE 'ncaahoopr%';
    
    SELECT COUNT(*) INTO hoopr_count
    FROM team_aliases
    WHERE source LIKE 'hoopr%';
    
    SELECT COUNT(*) INTO torvik_count
    FROM team_aliases
    WHERE source LIKE 'torvik%';
    
    RAISE NOTICE 'Migration 015 template: % ncaahoopR aliases, % hoopR aliases, % toRvik aliases',
        ncaahoopr_count, hoopr_count, torvik_count;
    RAISE NOTICE 'To import mappings, use: python services/prediction-service-python/scripts/import_standardized_team_mappings.py';
END;
$$;

COMMENT ON TABLE team_aliases IS 
    'Team name aliases from multiple sources. Use import_standardized_team_mappings.py to import from R packages (ncaahoopR, hoopR, toRvik).';
