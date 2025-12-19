-- Team Name Resolution Helper Function
-- Provides a single function to resolve team name variants to canonical names
-- Uses team_aliases table for accurate mapping across data sources

CREATE OR REPLACE FUNCTION resolve_team_name(input_name TEXT) 
RETURNS TEXT AS $$
    SELECT t.canonical_name 
    FROM teams t
    LEFT JOIN team_aliases ta ON t.id = ta.team_id
    WHERE LOWER(t.canonical_name) = LOWER(input_name)
       OR LOWER(ta.alias) = LOWER(input_name)
    LIMIT 1;
$$ LANGUAGE SQL STABLE;

-- Example usage:
-- SELECT resolve_team_name('Duke Blue Devils');  -- Returns 'Duke'
-- SELECT resolve_team_name('UNC');                -- Returns 'North Carolina' (if alias exists)
-- SELECT resolve_team_name('N.C. State');         -- Returns 'N.C. St.' (if alias exists)

COMMENT ON FUNCTION resolve_team_name IS 'Resolves team name variants to canonical names using team_aliases table';
