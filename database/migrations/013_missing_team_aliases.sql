-- ═══════════════════════════════════════════════════════════════════════════════
-- MIGRATION 013: Missing Team Aliases Fix (Dec 2025)
-- ═══════════════════════════════════════════════════════════════════════════════
--
-- Purpose: Add missing team aliases identified from production data quality checks.
-- These teams have Odds API names that don't match Barttorvik canonical names.
--
-- Unresolved teams identified:
-- 1. "Florida Int'l Golden Panthers" -> "Florida International" (CUSA)
-- 2. "Pennsylvania Quakers" -> "Penn" (Ivy)
-- 3. "N Colorado Bears" -> "Northern Colorado" (Big Sky) - NEW TEAM
-- 4. "Omaha" variants -> "Omaha" (Summit)
-- 5. "UL Monroe" clarifications
--
-- ═══════════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────────────
-- STEP 1: Add missing teams that don't exist yet
-- ─────────────────────────────────────────────────────────────────────────────────

INSERT INTO teams (canonical_name, barttorvik_name, conference) VALUES
-- Big Sky Conference (missing teams)
('Northern Colorado', 'Northern Colorado', 'Big Sky'),
('Montana', 'Montana', 'Big Sky'),
('Montana St.', 'Montana St.', 'Big Sky'),
('Weber St.', 'Weber St.', 'Big Sky'),
('Idaho St.', 'Idaho St.', 'Big Sky'),
('Portland St.', 'Portland St.', 'Big Sky'),
('Sacramento St.', 'Sacramento St.', 'Big Sky'),
('Eastern Washington', 'Eastern Washington', 'Big Sky'),
('Northern Arizona', 'Northern Arizona', 'Big Sky'),
('Idaho', 'Idaho', 'Big Sky'),

-- ASUN Conference (missing)
('Lipscomb', 'Lipscomb', 'ASUN'),
('Liberty', 'Liberty', 'ASUN'),
('Jacksonville', 'Jacksonville', 'ASUN'),
('Kennesaw St.', 'Kennesaw St.', 'ASUN'),
('North Alabama', 'North Alabama', 'ASUN'),
('Central Arkansas', 'Central Arkansas', 'ASUN'),
('NJIT', 'NJIT', 'ASUN'),
('Bellarmine', 'Bellarmine', 'ASUN'),
('Queens', 'Queens', 'ASUN'),
('Stetson', 'Stetson', 'ASUN'),
('Austin Peay', 'Austin Peay', 'ASUN'),
('Eastern Kentucky', 'Eastern Kentucky', 'ASUN'),

-- Southland Conference (missing)
('Southeastern Louisiana', 'Southeastern Louisiana', 'Southland'),
('McNeese', 'McNeese', 'Southland'),
('Nicholls', 'Nicholls', 'Southland'),
('Northwestern St.', 'Northwestern St.', 'Southland'),
('New Orleans', 'New Orleans', 'Southland'),
('Houston Christian', 'Houston Christian', 'Southland'),
('Incarnate Word', 'Incarnate Word', 'Southland'),
('Texas A&M Corpus Christi', 'Texas A&M Corpus Christi', 'Southland'),
('Lamar', 'Lamar', 'Southland'),

-- WAC (missing)
('Grand Canyon', 'Grand Canyon', 'WAC'),
('Seattle', 'Seattle', 'WAC'),
('Abilene Christian', 'Abilene Christian', 'WAC'),
('Tarleton St.', 'Tarleton St.', 'WAC'),
('Utah Valley', 'Utah Valley', 'WAC'),
('California Baptist', 'California Baptist', 'WAC'),
('UT Rio Grande Valley', 'UT Rio Grande Valley', 'WAC'),
('Utah Tech', 'Utah Tech', 'WAC'),
('Southern Utah', 'Southern Utah', 'WAC'),

-- Patriot League (missing)
('Army', 'Army', 'Patriot'),
('Navy', 'Navy', 'Patriot'),
('Lehigh', 'Lehigh', 'Patriot'),
('Lafayette', 'Lafayette', 'Patriot'),
('Bucknell', 'Bucknell', 'Patriot'),
('Colgate', 'Colgate', 'Patriot'),
('Holy Cross', 'Holy Cross', 'Patriot'),
('Boston U.', 'Boston U.', 'Patriot'),
('American', 'American', 'Patriot'),
('Loyola MD', 'Loyola MD', 'Patriot'),

-- Big South (missing)
('Campbell', 'Campbell', 'Big South'),
('High Point', 'High Point', 'Big South'),
('Longwood', 'Longwood', 'Big South'),
('Winthrop', 'Winthrop', 'Big South'),
('UNC Asheville', 'UNC Asheville', 'Big South'),
('Gardner Webb', 'Gardner Webb', 'Big South'),
('Presbyterian', 'Presbyterian', 'Big South'),
('Charleston So.', 'Charleston So.', 'Big South'),
('USC Upstate', 'USC Upstate', 'Big South'),
('Radford', 'Radford', 'Big South'),

-- Southern Conference (missing)
('Furman', 'Furman', 'Southern'),
('Chattanooga', 'Chattanooga', 'Southern'),
('ETSU', 'ETSU', 'Southern'),
('UNC Greensboro', 'UNC Greensboro', 'Southern'),
('VMI', 'VMI', 'Southern'),
('Wofford', 'Wofford', 'Southern'),
('Samford', 'Samford', 'Southern'),
('Mercer', 'Mercer', 'Southern'),
('Western Carolina', 'Western Carolina', 'Southern'),
('The Citadel', 'The Citadel', 'Southern'),

-- OVC (missing)
('Morehead St.', 'Morehead St.', 'OVC'),
('Southeast Missouri St.', 'Southeast Missouri St.', 'OVC'),
('Tennessee St.', 'Tennessee St.', 'OVC'),
('UT Martin', 'UT Martin', 'OVC'),
('Tennessee Tech', 'Tennessee Tech', 'OVC'),
('Little Rock', 'Little Rock', 'OVC'),
('SIU Edwardsville', 'SIU Edwardsville', 'OVC'),
('Lindenwood', 'Lindenwood', 'OVC'),
('Western Illinois', 'Western Illinois', 'OVC'),
('Southern Indiana', 'Southern Indiana', 'OVC'),

-- America East (missing)
('Vermont', 'Vermont', 'America East'),
('UMBC', 'UMBC', 'America East'),
('Binghamton', 'Binghamton', 'America East'),
('Maine', 'Maine', 'America East'),
('New Hampshire', 'New Hampshire', 'America East'),
('NJIT', 'NJIT', 'America East'),
('Albany', 'Albany', 'America East'),
('UMass Lowell', 'UMass Lowell', 'America East'),
('Bryant', 'Bryant', 'America East'),

-- Atlantic Sun / Sun Belt additions
('Stephen F. Austin', 'Stephen F. Austin', 'WAC')
ON CONFLICT (canonical_name) DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────────
-- STEP 2: Add specific missing aliases for unresolved teams
-- ─────────────────────────────────────────────────────────────────────────────────

-- Florida International / FIU (CRITICAL - Odds API sends "Florida Int'l Golden Panthers")
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    ('Florida International', 'Florida Int''l Golden Panthers'),
    ('Florida International', 'Florida Int''l'),
    ('Florida International', 'Fla Int''l'),
    ('Florida International', 'Florida Intl'),
    ('Florida International', 'FIU'),
    ('Florida International', 'FIU Golden Panthers'),
    ('Florida International', 'FIU Panthers'),
    ('Florida International', 'Florida International Golden Panthers'),
    ('Florida International', 'Florida International Panthers')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- Penn / Pennsylvania (CRITICAL - Odds API sends "Pennsylvania Quakers")
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    ('Penn', 'Pennsylvania'),
    ('Penn', 'Pennsylvania Quakers'),
    ('Penn', 'Penn Quakers'),
    ('Penn', 'UPenn'),
    ('Penn', 'U Penn'),
    ('Penn', 'Quakers')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- Northern Colorado (CRITICAL - Odds API sends "N Colorado Bears")
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    ('Northern Colorado', 'N Colorado Bears'),
    ('Northern Colorado', 'N Colorado'),
    ('Northern Colorado', 'N. Colorado'),
    ('Northern Colorado', 'Northern Colorado Bears'),
    ('Northern Colorado', 'UNC Bears'),
    ('Northern Colorado', 'North Colorado'),
    ('Northern Colorado', 'No. Colorado'),
    ('Northern Colorado', 'No Colorado')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- Omaha / Nebraska-Omaha variants
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    ('Omaha', 'Nebraska Omaha'),
    ('Omaha', 'Nebraska-Omaha'),
    ('Omaha', 'UNO'),
    ('Omaha', 'Omaha Mavericks'),
    ('Omaha', 'Nebraska Omaha Mavericks'),
    ('Omaha', 'UNO Mavericks')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- UL Monroe clarifications (canonical is "UL Monroe" per 005_complete_team_data.sql)
-- Note: 011 incorrectly had "Louisiana Monroe" as canonical - fixing here
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    ('UL Monroe', 'Louisiana Monroe'),
    ('UL Monroe', 'Louisiana-Monroe'),
    ('UL Monroe', 'ULM'),
    ('UL Monroe', 'UL Monroe Warhawks'),
    ('UL Monroe', 'Louisiana Monroe Warhawks'),
    ('UL Monroe', 'Warhawks')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- Seattle University (WAC)
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    ('Seattle', 'Seattle University'),
    ('Seattle', 'Seattle U'),
    ('Seattle', 'Seattle Redhawks'),
    ('Seattle', 'Seattle University Redhawks')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- Other commonly missed aliases
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    -- Wichita State variants
    ('Wichita St.', 'Wichita St Shockers'),
    ('Wichita St.', 'Wichita State Shockers'),
    
    -- Nicholls State
    ('Nicholls', 'Nicholls St'),
    ('Nicholls', 'Nicholls St.'),
    ('Nicholls', 'Nicholls State'),
    ('Nicholls', 'Nicholls St Colonels'),
    ('Nicholls', 'Nicholls State Colonels'),
    
    -- Oregon State
    ('Oregon St.', 'Ore St'),
    ('Oregon St.', 'Ore. St.'),
    
    -- Washington State
    ('Washington St.', 'Wash St'),
    ('Washington St.', 'Wash. St.'),
    ('Washington St.', 'WSU'),
    ('Washington St.', 'Washington State'),
    ('Washington St.', 'Washington State Cougars'),
    
    -- McNeese
    ('McNeese', 'McNeese St.'),
    ('McNeese', 'McNeese St'),
    ('McNeese', 'McNeese State'),
    ('McNeese', 'McNeese State Cowboys'),
    
    -- UNI (Northern Iowa)
    ('UNI', 'Northern Iowa'),
    ('UNI', 'Northern Iowa Panthers'),
    
    -- Western Carolina
    ('Western Carolina', 'Western Carolina Catamounts'),
    ('Western Carolina', 'W Carolina'),
    ('Western Carolina', 'WCU'),
    ('Western Carolina', 'Catamounts'),
    
    -- UT Rio Grande Valley
    ('UT Rio Grande Valley', 'UTRGV'),
    ('UT Rio Grande Valley', 'Texas Rio Grande Valley'),
    ('UT Rio Grande Valley', 'Rio Grande Valley'),
    ('UT Rio Grande Valley', 'UTRGV Vaqueros'),
    
    -- Loyola MD
    ('Loyola MD', 'Loyola Maryland'),
    ('Loyola MD', 'Loyola (MD)'),
    ('Loyola MD', 'Loyola Maryland Greyhounds'),
    
    -- Boise State
    ('Boise St.', 'Boise St'),
    
    -- New Mexico
    ('New Mexico', 'UNM'),
    ('New Mexico', 'New Mexico Lobos')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────────
-- STEP 3: Fix any orphaned team_id references in team_aliases
-- (where aliases point to non-existent team_ids)
-- ─────────────────────────────────────────────────────────────────────────────────

-- Clean up any orphaned aliases
DELETE FROM team_aliases
WHERE team_id NOT IN (SELECT id FROM teams);

-- ─────────────────────────────────────────────────────────────────────────────────
-- STEP 4: Log migration completion
-- ─────────────────────────────────────────────────────────────────────────────────

DO $$
DECLARE
    alias_count INTEGER;
    team_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO team_count FROM teams;
    SELECT COUNT(*) INTO alias_count FROM team_aliases;
    RAISE NOTICE 'Migration 013 complete: % teams, % aliases', team_count, alias_count;
END;
$$;
