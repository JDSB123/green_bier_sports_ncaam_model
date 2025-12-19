-- Team Name Resolution Helper Function
-- Provides a single function to resolve team name variants to canonical names
-- Uses team_aliases table for accurate mapping across data sources

-- Resolve team name - PREFERS teams that have ratings (from Barttorvik)
-- This ensures Odds API names map to Barttorvik canonical names, not duplicates
CREATE OR REPLACE FUNCTION resolve_team_name(input_name TEXT) 
RETURNS TEXT AS $$
    SELECT t.canonical_name 
    FROM teams t
    LEFT JOIN team_aliases ta ON t.id = ta.team_id
    LEFT JOIN team_ratings tr ON t.id = tr.team_id
    WHERE LOWER(t.canonical_name) = LOWER(input_name)
       OR LOWER(ta.alias) = LOWER(input_name)
    ORDER BY tr.team_id IS NOT NULL DESC, t.canonical_name
    LIMIT 1;
$$ LANGUAGE SQL STABLE;

-- Example usage:
-- SELECT resolve_team_name('Duke Blue Devils');  -- Returns 'Duke'
-- SELECT resolve_team_name('UNC');                -- Returns 'North Carolina' (if alias exists)
-- SELECT resolve_team_name('N.C. State');         -- Returns 'N.C. St.' (if alias exists)

COMMENT ON FUNCTION resolve_team_name IS 'Resolves team name variants to canonical names using team_aliases table';
