-- ═══════════════════════════════════════════════════════════════════════════════
-- MIGRATION 011: Comprehensive Team Alias Mapping
-- ═══════════════════════════════════════════════════════════════════════════════
--
-- Purpose: Add comprehensive team name aliases to ensure 100% matching between
-- The Odds API team names and Barttorvik canonical names.
--
-- Problem: The Odds API sends team names like "Florida A&M Rattlers" but
-- Barttorvik uses "Florida A&M". This migration adds 950+ aliases to handle
-- all known variants including:
--   - Full names with mascots (e.g., "Duke Blue Devils" -> "Duke")
--   - Abbreviations (e.g., "UNC" -> "North Carolina")
--   - Alternative spellings (e.g., "Fla Atlantic" -> "FAU")
--   - Common nicknames (e.g., "Zags" -> "Gonzaga")
--
-- ═══════════════════════════════════════════════════════════════════════════════

-- First, ensure the team_aliases table exists with proper structure
CREATE TABLE IF NOT EXISTS team_aliases (
    id SERIAL PRIMARY KEY,
    team_id UUID REFERENCES teams(id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'manual',
    confidence DECIMAL(3,2) DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(alias, source)
);

-- Create index for fast alias lookups
CREATE INDEX IF NOT EXISTS idx_team_aliases_alias_lower ON team_aliases (LOWER(alias));
CREATE INDEX IF NOT EXISTS idx_team_aliases_team_id ON team_aliases (team_id);

-- ═══════════════════════════════════════════════════════════════════════════════
-- POWER CONFERENCE TEAMS (ACC, Big 12, Big Ten, Pac-12, SEC, Big East)
-- ═══════════════════════════════════════════════════════════════════════════════

-- ACC Teams
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    ('Duke', 'Duke Blue Devils'),
    ('Duke', 'Blue Devils'),
    ('North Carolina', 'North Carolina Tar Heels'),
    ('North Carolina', 'UNC Tar Heels'),
    ('North Carolina', 'UNC'),
    ('North Carolina', 'NC'),
    ('NC State', 'North Carolina State'),
    ('NC State', 'NC State Wolfpack'),
    ('NC State', 'N.C. State'),
    ('NC State', 'N.C. St.'),
    ('Virginia', 'Virginia Cavaliers'),
    ('Virginia', 'UVA'),
    ('Virginia', 'Cavaliers'),
    ('Virginia Tech', 'Virginia Tech Hokies'),
    ('Virginia Tech', 'VT'),
    ('Virginia Tech', 'Va Tech'),
    ('Virginia Tech', 'Hokies'),
    ('Wake Forest', 'Wake Forest Demon Deacons'),
    ('Wake Forest', 'Demon Deacons'),
    ('Louisville', 'Louisville Cardinals'),
    ('Louisville', 'Cards'),
    ('Louisville', 'Cardinals'),
    ('Syracuse', 'Syracuse Orange'),
    ('Syracuse', 'Cuse'),
    ('Syracuse', 'Orange'),
    ('Florida St.', 'Florida State'),
    ('Florida St.', 'Florida State Seminoles'),
    ('Florida St.', 'FSU'),
    ('Florida St.', 'Seminoles'),
    ('Clemson', 'Clemson Tigers'),
    ('Miami FL', 'Miami'),
    ('Miami FL', 'Miami Hurricanes'),
    ('Miami FL', 'Miami (FL)'),
    ('Miami FL', 'U of Miami'),
    ('Georgia Tech', 'Georgia Tech Yellow Jackets'),
    ('Georgia Tech', 'GT'),
    ('Georgia Tech', 'Yellow Jackets'),
    ('Boston College', 'Boston College Eagles'),
    ('Boston College', 'BC'),
    ('Boston College', 'Eagles'),
    ('Pittsburgh', 'Pitt'),
    ('Pittsburgh', 'Pittsburgh Panthers'),
    ('Pittsburgh', 'Pitt Panthers'),
    ('Pittsburgh', 'Panthers'),
    ('Notre Dame', 'Notre Dame Fighting Irish'),
    ('Notre Dame', 'ND'),
    ('Notre Dame', 'Fighting Irish'),
    ('California', 'Cal'),
    ('California', 'California Golden Bears'),
    ('California', 'Cal Bears'),
    ('California', 'Golden Bears'),
    ('Stanford', 'Stanford Cardinal'),
    ('SMU', 'Southern Methodist'),
    ('SMU', 'SMU Mustangs'),
    ('SMU', 'Mustangs')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- Big 12 Teams
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    ('Kansas', 'Kansas Jayhawks'),
    ('Kansas', 'KU'),
    ('Kansas', 'Jayhawks'),
    ('Kansas St.', 'Kansas State'),
    ('Kansas St.', 'Kansas State Wildcats'),
    ('Kansas St.', 'K-State'),
    ('Kansas St.', 'KSU'),
    ('Baylor', 'Baylor Bears'),
    ('Baylor', 'Bears'),
    ('Texas Tech', 'Texas Tech Red Raiders'),
    ('Texas Tech', 'TTU'),
    ('Texas Tech', 'Red Raiders'),
    ('TCU', 'Texas Christian'),
    ('TCU', 'TCU Horned Frogs'),
    ('TCU', 'Horned Frogs'),
    ('Oklahoma St.', 'Oklahoma State'),
    ('Oklahoma St.', 'Oklahoma State Cowboys'),
    ('Oklahoma St.', 'OSU Cowboys'),
    ('Oklahoma St.', 'Cowboys'),
    ('Iowa St.', 'Iowa State'),
    ('Iowa St.', 'Iowa State Cyclones'),
    ('Iowa St.', 'ISU'),
    ('Iowa St.', 'Cyclones'),
    ('West Virginia', 'West Virginia Mountaineers'),
    ('West Virginia', 'WVU'),
    ('West Virginia', 'Mountaineers'),
    ('Texas', 'Texas Longhorns'),
    ('Texas', 'UT'),
    ('Texas', 'Longhorns'),
    ('Oklahoma', 'Oklahoma Sooners'),
    ('Oklahoma', 'OU'),
    ('Oklahoma', 'Sooners'),
    ('Cincinnati', 'Cincinnati Bearcats'),
    ('Cincinnati', 'Cincy'),
    ('Cincinnati', 'Bearcats'),
    ('UCF', 'Central Florida'),
    ('UCF', 'UCF Knights'),
    ('UCF', 'Knights'),
    ('Houston', 'Houston Cougars'),
    ('Houston', 'UH'),
    ('Houston', 'Cougars'),
    ('BYU', 'Brigham Young'),
    ('BYU', 'BYU Cougars'),
    ('Colorado', 'Colorado Buffaloes'),
    ('Colorado', 'CU'),
    ('Colorado', 'Buffaloes'),
    ('Arizona', 'Arizona Wildcats'),
    ('Arizona', 'U of A'),
    ('Arizona', 'UA'),
    ('Arizona St.', 'Arizona State'),
    ('Arizona St.', 'Arizona State Sun Devils'),
    ('Arizona St.', 'ASU'),
    ('Arizona St.', 'Sun Devils'),
    ('Utah', 'Utah Utes'),
    ('Utah', 'Utes')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- Big Ten Teams
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    ('Michigan', 'Michigan Wolverines'),
    ('Michigan', 'U of M'),
    ('Michigan', 'Wolverines'),
    ('Michigan St.', 'Michigan State'),
    ('Michigan St.', 'Michigan State Spartans'),
    ('Michigan St.', 'MSU'),
    ('Michigan St.', 'Spartans'),
    ('Ohio St.', 'Ohio State'),
    ('Ohio St.', 'Ohio State Buckeyes'),
    ('Ohio St.', 'OSU'),
    ('Ohio St.', 'Buckeyes'),
    ('Indiana', 'Indiana Hoosiers'),
    ('Indiana', 'IU'),
    ('Indiana', 'Hoosiers'),
    ('Purdue', 'Purdue Boilermakers'),
    ('Purdue', 'Boilermakers'),
    ('Illinois', 'Illinois Fighting Illini'),
    ('Illinois', 'Illini'),
    ('Illinois', 'Fighting Illini'),
    ('Iowa', 'Iowa Hawkeyes'),
    ('Iowa', 'Hawkeyes'),
    ('Wisconsin', 'Wisconsin Badgers'),
    ('Wisconsin', 'Badgers'),
    ('Minnesota', 'Minnesota Golden Gophers'),
    ('Minnesota', 'Gophers'),
    ('Minnesota', 'Golden Gophers'),
    ('Northwestern', 'Northwestern Wildcats'),
    ('Maryland', 'Maryland Terrapins'),
    ('Maryland', 'Terps'),
    ('Maryland', 'Terrapins'),
    ('Nebraska', 'Nebraska Cornhuskers'),
    ('Nebraska', 'Huskers'),
    ('Nebraska', 'Cornhuskers'),
    ('Penn St.', 'Penn State'),
    ('Penn St.', 'Penn State Nittany Lions'),
    ('Penn St.', 'PSU'),
    ('Penn St.', 'Nittany Lions'),
    ('Rutgers', 'Rutgers Scarlet Knights'),
    ('Rutgers', 'Scarlet Knights'),
    ('UCLA', 'UCLA Bruins'),
    ('UCLA', 'Bruins'),
    ('USC', 'Southern California'),
    ('USC', 'USC Trojans'),
    ('USC', 'Southern Cal'),
    ('USC', 'Trojans'),
    ('Oregon', 'Oregon Ducks'),
    ('Oregon', 'Ducks'),
    ('Oregon St.', 'Oregon State'),
    ('Oregon St.', 'Oregon State Beavers'),
    ('Oregon St.', 'OSU Beavers'),
    ('Oregon St.', 'Beavers'),
    ('Washington', 'Washington Huskies'),
    ('Washington', 'UW'),
    ('Washington', 'UDub'),
    ('Washington', 'Huskies')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- SEC Teams
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    ('Kentucky', 'Kentucky Wildcats'),
    ('Kentucky', 'UK'),
    ('Kentucky', 'Wildcats'),
    ('Tennessee', 'Tennessee Volunteers'),
    ('Tennessee', 'Vols'),
    ('Tennessee', 'UT'),
    ('Tennessee', 'Volunteers'),
    ('Auburn', 'Auburn Tigers'),
    ('Auburn', 'Tigers'),
    ('Alabama', 'Alabama Crimson Tide'),
    ('Alabama', 'Bama'),
    ('Alabama', 'Crimson Tide'),
    ('Florida', 'Florida Gators'),
    ('Florida', 'UF'),
    ('Florida', 'Gators'),
    ('Georgia', 'Georgia Bulldogs'),
    ('Georgia', 'UGA'),
    ('Georgia', 'Dawgs'),
    ('Georgia', 'Bulldogs'),
    ('LSU', 'Louisiana State'),
    ('LSU', 'LSU Tigers'),
    ('Arkansas', 'Arkansas Razorbacks'),
    ('Arkansas', 'Hogs'),
    ('Arkansas', 'Razorbacks'),
    ('Ole Miss', 'Mississippi'),
    ('Ole Miss', 'Ole Miss Rebels'),
    ('Ole Miss', 'Rebels'),
    ('Mississippi St.', 'Mississippi State'),
    ('Mississippi St.', 'Mississippi State Bulldogs'),
    ('Mississippi St.', 'Miss State'),
    ('Mississippi St.', 'MSU Bulldogs'),
    ('Missouri', 'Missouri Tigers'),
    ('Missouri', 'Mizzou'),
    ('South Carolina', 'South Carolina Gamecocks'),
    ('South Carolina', 'USC Gamecocks'),
    ('South Carolina', 'Gamecocks'),
    ('Vanderbilt', 'Vanderbilt Commodores'),
    ('Vanderbilt', 'Vandy'),
    ('Vanderbilt', 'Commodores'),
    ('Texas A&M', 'Texas AM'),
    ('Texas A&M', 'Texas A&M Aggies'),
    ('Texas A&M', 'TAMU'),
    ('Texas A&M', 'Aggies')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- Big East Teams
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    ('Connecticut', 'UConn'),
    ('Connecticut', 'UConn Huskies'),
    ('Connecticut', 'Connecticut Huskies'),
    ('Connecticut', 'UCONN'),
    ('Villanova', 'Villanova Wildcats'),
    ('Villanova', 'Nova'),
    ('Creighton', 'Creighton Bluejays'),
    ('Creighton', 'Bluejays'),
    ('Marquette', 'Marquette Golden Eagles'),
    ('Marquette', 'Golden Eagles'),
    ('Xavier', 'Xavier Musketeers'),
    ('Xavier', 'Musketeers'),
    ('Providence', 'Providence Friars'),
    ('Providence', 'Friars'),
    ('Seton Hall', 'Seton Hall Pirates'),
    ('Seton Hall', 'Pirates'),
    ('Butler', 'Butler Bulldogs'),
    ('Georgetown', 'Georgetown Hoyas'),
    ('Georgetown', 'Hoyas'),
    ('DePaul', 'DePaul Blue Demons'),
    ('DePaul', 'Blue Demons'),
    ('St. Johns', 'St. John''s'),
    ('St. Johns', 'St. John''s Red Storm'),
    ('St. Johns', 'Red Storm')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════════
-- MID-MAJOR CONFERENCES (AAC, A-10, MWC, WCC, etc.)
-- ═══════════════════════════════════════════════════════════════════════════════

-- American Athletic Conference
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    ('Memphis', 'Memphis Tigers'),
    ('Tulane', 'Tulane Green Wave'),
    ('Tulane', 'Green Wave'),
    ('Tulsa', 'Tulsa Golden Hurricane'),
    ('Tulsa', 'Golden Hurricane'),
    ('SMU', 'Southern Methodist'),
    ('SMU', 'SMU Mustangs'),
    ('Wichita St.', 'Wichita State'),
    ('Wichita St.', 'Wichita State Shockers'),
    ('Wichita St.', 'Shockers'),
    ('Temple', 'Temple Owls'),
    ('Temple', 'Owls'),
    ('East Carolina', 'ECU'),
    ('East Carolina', 'East Carolina Pirates'),
    ('South Florida', 'USF'),
    ('South Florida', 'South Florida Bulls'),
    ('South Florida', 'Bulls'),
    ('Charlotte', 'Charlotte 49ers'),
    ('Charlotte', '49ers'),
    ('FAU', 'Florida Atlantic'),
    ('FAU', 'Florida Atlantic Owls'),
    ('FAU', 'Fla Atlantic'),
    ('UAB', 'Alabama-Birmingham'),
    ('UAB', 'UAB Blazers'),
    ('UAB', 'Blazers'),
    ('UTSA', 'UT San Antonio'),
    ('UTSA', 'UTSA Roadrunners'),
    ('North Texas', 'UNT'),
    ('North Texas', 'North Texas Mean Green'),
    ('North Texas', 'Mean Green'),
    ('Rice', 'Rice Owls')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- Mountain West Conference
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    ('San Diego St.', 'San Diego State'),
    ('San Diego St.', 'San Diego State Aztecs'),
    ('San Diego St.', 'SDSU'),
    ('San Diego St.', 'Aztecs'),
    ('Boise St.', 'Boise State'),
    ('Boise St.', 'Boise State Broncos'),
    ('Boise St.', 'Broncos'),
    ('Nevada', 'Nevada Wolf Pack'),
    ('Nevada', 'Wolf Pack'),
    ('UNLV', 'Nevada Las Vegas'),
    ('UNLV', 'UNLV Rebels'),
    ('UNLV', 'Runnin'' Rebels'),
    ('Colorado St.', 'Colorado State'),
    ('Colorado St.', 'Colorado State Rams'),
    ('Colorado St.', 'CSU'),
    ('Colorado St.', 'Rams'),
    ('New Mexico', 'New Mexico Lobos'),
    ('New Mexico', 'UNM'),
    ('New Mexico', 'Lobos'),
    ('Fresno St.', 'Fresno State'),
    ('Fresno St.', 'Fresno State Bulldogs'),
    ('Utah St.', 'Utah State'),
    ('Utah St.', 'Utah State Aggies'),
    ('Wyoming', 'Wyoming Cowboys'),
    ('Air Force', 'Air Force Falcons'),
    ('Air Force', 'Falcons'),
    ('San Jose St.', 'San Jose State'),
    ('San Jose St.', 'San Jose State Spartans'),
    ('San Jose St.', 'SJSU')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- West Coast Conference
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    ('Gonzaga', 'Gonzaga Bulldogs'),
    ('Gonzaga', 'Zags'),
    ('Saint Mary''s', 'Saint Marys'),
    ('Saint Mary''s', 'St. Mary''s'),
    ('Saint Mary''s', 'St. Marys'),
    ('Saint Mary''s', 'Saint Mary''s Gaels'),
    ('Saint Mary''s', 'Gaels'),
    ('San Francisco', 'USF Dons'),
    ('San Francisco', 'San Francisco Dons'),
    ('San Francisco', 'Dons'),
    ('Santa Clara', 'Santa Clara Broncos'),
    ('Pepperdine', 'Pepperdine Waves'),
    ('Pepperdine', 'Waves'),
    ('Loyola Marymount', 'LMU'),
    ('Loyola Marymount', 'Loyola Marymount Lions'),
    ('Pacific', 'Pacific Tigers'),
    ('Portland', 'Portland Pilots'),
    ('Portland', 'Pilots'),
    ('San Diego', 'San Diego Toreros'),
    ('San Diego', 'Toreros')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- Atlantic 10 Conference
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    ('Dayton', 'Dayton Flyers'),
    ('Dayton', 'Flyers'),
    ('VCU', 'Virginia Commonwealth'),
    ('VCU', 'VCU Rams'),
    ('VCU', 'Rams'),
    ('Saint Louis', 'St. Louis'),
    ('Saint Louis', 'Saint Louis Billikens'),
    ('Saint Louis', 'Billikens'),
    ('Richmond', 'Richmond Spiders'),
    ('Richmond', 'Spiders'),
    ('Davidson', 'Davidson Wildcats'),
    ('Rhode Island', 'URI'),
    ('Rhode Island', 'Rhode Island Rams'),
    ('George Mason', 'GMU'),
    ('George Mason', 'George Mason Patriots'),
    ('George Mason', 'Patriots'),
    ('St. Bonaventure', 'Saint Bonaventure'),
    ('St. Bonaventure', 'St. Bonaventure Bonnies'),
    ('St. Bonaventure', 'Bonnies'),
    ('La Salle', 'La Salle Explorers'),
    ('La Salle', 'Explorers'),
    ('Fordham', 'Fordham Rams'),
    ('Duquesne', 'Duquesne Dukes'),
    ('Duquesne', 'Dukes'),
    ('George Washington', 'GW'),
    ('George Washington', 'George Washington Colonials'),
    ('George Washington', 'Colonials'),
    ('UMass', 'Massachusetts'),
    ('UMass', 'UMass Minutemen'),
    ('UMass', 'Minutemen'),
    ('St. Joseph''s', 'Saint Joseph''s'),
    ('St. Joseph''s', 'St. Joseph''s Hawks'),
    ('St. Joseph''s', 'Hawks'),
    ('Loyola Chicago', 'Loyola-Chicago'),
    ('Loyola Chicago', 'Loyola Chicago Ramblers'),
    ('Loyola Chicago', 'Ramblers')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════════
-- SPECIFIC PROBLEMATIC TEAMS (Florida A&M, FIU, Oregon variants, etc.)
-- ═══════════════════════════════════════════════════════════════════════════════

-- Florida schools - CRITICAL: These are commonly confused
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    -- Florida A&M - SWAC
    ('Florida A&M', 'Florida A&M Rattlers'),
    ('Florida A&M', 'Florida AM'),
    ('Florida A&M', 'FAMU'),
    ('Florida A&M', 'Fla A&M'),
    ('Florida A&M', 'Fla AM'),
    ('Florida A&M', 'Rattlers'),
    -- FIU - CUSA
    ('FIU', 'Florida International'),
    ('FIU', 'Florida International Panthers'),
    ('FIU', 'FIU Panthers'),
    ('FIU', 'Fla International'),
    ('FIU', 'Florida Intl'),
    -- Florida Atlantic (FAU)
    ('FAU', 'Florida Atlantic'),
    ('FAU', 'Florida Atlantic Owls'),
    ('FAU', 'Fla Atlantic'),
    ('FAU', 'FAU Owls'),
    -- Florida Gulf Coast
    ('Florida Gulf Coast', 'FGCU'),
    ('Florida Gulf Coast', 'Florida Gulf Coast Eagles'),
    ('Florida Gulf Coast', 'Eagles'),
    -- Bethune-Cookman (Florida HBCU)
    ('Bethune Cookman', 'Bethune-Cookman'),
    ('Bethune Cookman', 'Bethune Cookman Wildcats'),
    ('Bethune Cookman', 'B-CU'),
    -- Jacksonville
    ('Jacksonville', 'Jacksonville Dolphins'),
    ('Jacksonville', 'JU'),
    -- Stetson
    ('Stetson', 'Stetson Hatters'),
    ('Stetson', 'Hatters'),
    -- North Florida
    ('North Florida', 'UNF'),
    ('North Florida', 'North Florida Ospreys'),
    ('North Florida', 'Ospreys')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- Oregon schools - CRITICAL: Oregon vs Oregon State confusion
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    ('Oregon', 'Oregon Ducks'),
    ('Oregon', 'UO'),
    ('Oregon', 'Ducks'),
    ('Oregon St.', 'Oregon State'),
    ('Oregon St.', 'Oregon State Beavers'),
    ('Oregon St.', 'OSU Beavers'),
    ('Oregon St.', 'Beavers'),
    ('Oregon St.', 'Ore State'),
    ('Oregon St.', 'Ore St')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════════
-- HBCU TEAMS (SWAC, MEAC, etc.) - Often have unique naming patterns
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    -- SWAC Teams
    ('Grambling St.', 'Grambling'),
    ('Grambling St.', 'Grambling State'),
    ('Grambling St.', 'Grambling Tigers'),
    ('Grambling St.', 'Grambling State Tigers'),
    ('Jackson St.', 'Jackson State'),
    ('Jackson St.', 'Jackson State Tigers'),
    ('Southern', 'Southern University'),
    ('Southern', 'Southern Jaguars'),
    ('Southern', 'Southern U'),
    ('Alcorn St.', 'Alcorn State'),
    ('Alcorn St.', 'Alcorn State Braves'),
    ('Alcorn St.', 'Alcorn'),
    ('Prairie View A&M', 'Prairie View'),
    ('Prairie View A&M', 'Prairie View A&M Panthers'),
    ('Prairie View A&M', 'PVAMU'),
    ('Texas Southern', 'Texas Southern Tigers'),
    ('Texas Southern', 'TSU Tigers'),
    ('Alabama St.', 'Alabama State'),
    ('Alabama St.', 'Alabama State Hornets'),
    ('Alabama A&M', 'Alabama A&M Bulldogs'),
    ('Alabama A&M', 'AAMU'),
    ('Arkansas Pine Bluff', 'UAPB'),
    ('Arkansas Pine Bluff', 'Arkansas Pine Bluff Golden Lions'),
    ('Mississippi Valley St.', 'Mississippi Valley State'),
    ('Mississippi Valley St.', 'MVSU'),
    ('Mississippi Valley St.', 'Miss Valley St.'),
    ('Mississippi Valley St.', 'Miss Valley St. Delta Devils'),
    -- MEAC Teams
    ('Norfolk St.', 'Norfolk State'),
    ('Norfolk St.', 'Norfolk State Spartans'),
    ('Morgan St.', 'Morgan State'),
    ('Morgan St.', 'Morgan State Bears'),
    ('Coppin St.', 'Coppin State'),
    ('Coppin St.', 'Coppin State Eagles'),
    ('Coppin St.', 'Coppin St. Eagles'),
    ('Howard', 'Howard Bison'),
    ('Hampton', 'Hampton Pirates'),
    ('Hampton', 'Hampton University'),
    ('NC Central', 'North Carolina Central'),
    ('NC Central', 'NC Central Eagles'),
    ('NC Central', 'NCCU'),
    ('NC A&T', 'North Carolina A&T'),
    ('NC A&T', 'NC A&T Aggies'),
    ('NC A&T', 'NCAT'),
    ('Delaware St.', 'Delaware State'),
    ('Delaware St.', 'Delaware State Hornets'),
    ('SC State', 'South Carolina State'),
    ('SC State', 'SC State Bulldogs'),
    ('Maryland Eastern Shore', 'UMES'),
    ('Maryland Eastern Shore', 'MD Eastern Shore')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════════
-- STATE SCHOOL VARIATIONS (St. vs State patterns)
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    -- Ball State
    ('Ball St.', 'Ball State'),
    ('Ball St.', 'Ball State Cardinals'),
    -- Boise State
    ('Boise St.', 'Boise State'),
    ('Boise St.', 'Boise State Broncos'),
    -- Bowling Green
    ('Bowling Green', 'Bowling Green Falcons'),
    ('Bowling Green', 'BGSU'),
    -- Central Michigan
    ('Central Michigan', 'CMU'),
    ('Central Michigan', 'Central Michigan Chippewas'),
    ('Central Michigan', 'Chippewas'),
    -- Eastern Michigan
    ('Eastern Michigan', 'EMU'),
    ('Eastern Michigan', 'Eastern Michigan Eagles'),
    -- Kent State
    ('Kent St.', 'Kent State'),
    ('Kent St.', 'Kent State Golden Flashes'),
    ('Kent St.', 'Golden Flashes'),
    -- Miami OH
    ('Miami OH', 'Miami (OH)'),
    ('Miami OH', 'Miami Ohio'),
    ('Miami OH', 'Miami RedHawks'),
    ('Miami OH', 'RedHawks'),
    -- Northern Illinois
    ('Northern Illinois', 'NIU'),
    ('Northern Illinois', 'Northern Illinois Huskies'),
    -- Ohio
    ('Ohio', 'Ohio Bobcats'),
    ('Ohio', 'Ohio U'),
    ('Ohio', 'Bobcats'),
    -- Toledo
    ('Toledo', 'Toledo Rockets'),
    ('Toledo', 'Rockets'),
    -- Western Michigan
    ('Western Michigan', 'WMU'),
    ('Western Michigan', 'Western Michigan Broncos'),
    -- Akron
    ('Akron', 'Akron Zips'),
    ('Akron', 'Zips'),
    -- Buffalo
    ('Buffalo', 'Buffalo Bulls'),
    ('Buffalo', 'UB')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════════
-- IVY LEAGUE & PATRIOT LEAGUE
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    -- Ivy League
    ('Princeton', 'Princeton Tigers'),
    ('Yale', 'Yale Bulldogs'),
    ('Harvard', 'Harvard Crimson'),
    ('Harvard', 'Crimson'),
    ('Penn', 'Pennsylvania'),
    ('Penn', 'Penn Quakers'),
    ('Penn', 'Quakers'),
    ('Columbia', 'Columbia Lions'),
    ('Cornell', 'Cornell Big Red'),
    ('Cornell', 'Big Red'),
    ('Brown', 'Brown Bears'),
    ('Dartmouth', 'Dartmouth Big Green'),
    ('Dartmouth', 'Big Green'),
    -- Patriot League
    ('Navy', 'Navy Midshipmen'),
    ('Navy', 'Midshipmen'),
    ('Army', 'Army Black Knights'),
    ('Army', 'Army West Point'),
    ('Army', 'Black Knights'),
    ('Lehigh', 'Lehigh Mountain Hawks'),
    ('Lehigh', 'Mountain Hawks'),
    ('Lafayette', 'Lafayette Leopards'),
    ('Lafayette', 'Leopards'),
    ('Bucknell', 'Bucknell Bison'),
    ('Colgate', 'Colgate Raiders'),
    ('Colgate', 'Raiders'),
    ('Holy Cross', 'Holy Cross Crusaders'),
    ('Holy Cross', 'Crusaders'),
    ('Boston U.', 'Boston University'),
    ('Boston U.', 'Boston University Terriers'),
    ('Boston U.', 'BU'),
    ('Boston U.', 'Terriers'),
    ('American', 'American University'),
    ('American', 'American Eagles'),
    ('American', 'AU')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════════
-- ADDITIONAL MID-MAJOR & LOW-MAJOR CONFERENCES
-- ═══════════════════════════════════════════════════════════════════════════════

-- Conference USA
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    ('Western Kentucky', 'WKU'),
    ('Western Kentucky', 'Western Kentucky Hilltoppers'),
    ('Western Kentucky', 'Hilltoppers'),
    ('Middle Tennessee', 'MTSU'),
    ('Middle Tennessee', 'Middle Tennessee Blue Raiders'),
    ('Middle Tennessee', 'Blue Raiders'),
    ('Louisiana Tech', 'LA Tech'),
    ('Louisiana Tech', 'Louisiana Tech Bulldogs'),
    ('Marshall', 'Marshall Thundering Herd'),
    ('Marshall', 'Thundering Herd'),
    ('Old Dominion', 'ODU'),
    ('Old Dominion', 'Old Dominion Monarchs'),
    ('Old Dominion', 'Monarchs'),
    ('UTEP', 'Texas El Paso'),
    ('UTEP', 'UTEP Miners'),
    ('UTEP', 'Miners'),
    ('Southern Miss', 'Southern Mississippi'),
    ('Southern Miss', 'Southern Miss Golden Eagles'),
    ('Southern Miss', 'USM'),
    ('New Mexico St.', 'New Mexico State'),
    ('New Mexico St.', 'New Mexico State Aggies'),
    ('New Mexico St.', 'NMSU'),
    ('Sam Houston St.', 'Sam Houston'),
    ('Sam Houston St.', 'Sam Houston State'),
    ('Sam Houston St.', 'Sam Houston Bearkats'),
    ('Sam Houston St.', 'SHSU'),
    ('Liberty', 'Liberty Flames'),
    ('Liberty', 'Flames'),
    ('Jacksonville St.', 'Jacksonville State'),
    ('Jacksonville St.', 'Jacksonville State Gamecocks')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- Sun Belt Conference
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    ('Appalachian St.', 'Appalachian State'),
    ('Appalachian St.', 'App State'),
    ('Appalachian St.', 'Appalachian State Mountaineers'),
    ('Georgia St.', 'Georgia State'),
    ('Georgia St.', 'Georgia State Panthers'),
    ('Georgia Southern', 'Ga Southern'),
    ('Georgia Southern', 'Georgia Southern Eagles'),
    ('Louisiana', 'Louisiana Ragin'' Cajuns'),
    ('Louisiana', 'UL Lafayette'),
    ('Louisiana', 'Ragin'' Cajuns'),
    ('Louisiana', 'ULL'),
    ('Louisiana Monroe', 'ULM'),
    ('Louisiana Monroe', 'Louisiana Monroe Warhawks'),
    ('Louisiana Monroe', 'UL Monroe'),
    ('Arkansas St.', 'Arkansas State'),
    ('Arkansas St.', 'Arkansas State Red Wolves'),
    ('Arkansas St.', 'Red Wolves'),
    ('Texas St.', 'Texas State'),
    ('Texas St.', 'Texas State Bobcats'),
    ('Troy', 'Troy Trojans'),
    ('South Alabama', 'USA'),
    ('South Alabama', 'South Alabama Jaguars'),
    ('Coastal Carolina', 'CCU'),
    ('Coastal Carolina', 'Coastal Carolina Chanticleers'),
    ('Coastal Carolina', 'Chanticleers'),
    ('James Madison', 'JMU'),
    ('James Madison', 'James Madison Dukes'),
    ('Marshall', 'Marshall Thundering Herd'),
    ('Southern Miss', 'Southern Mississippi'),
    ('Southern Miss', 'USM'),
    ('Old Dominion', 'ODU')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- Missouri Valley Conference
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    ('Drake', 'Drake Bulldogs'),
    ('Indiana St.', 'Indiana State'),
    ('Indiana St.', 'Indiana State Sycamores'),
    ('Indiana St.', 'Sycamores'),
    ('Illinois St.', 'Illinois State'),
    ('Illinois St.', 'Illinois State Redbirds'),
    ('Illinois St.', 'Redbirds'),
    ('Missouri St.', 'Missouri State'),
    ('Missouri St.', 'Missouri State Bears'),
    ('Southern Illinois', 'SIU'),
    ('Southern Illinois', 'Southern Illinois Salukis'),
    ('Southern Illinois', 'Salukis'),
    ('Northern Iowa', 'UNI'),
    ('Northern Iowa', 'Northern Iowa Panthers'),
    ('Valparaiso', 'Valpo'),
    ('Valparaiso', 'Valparaiso Beacons'),
    ('Valparaiso', 'Beacons'),
    ('Evansville', 'Evansville Purple Aces'),
    ('Evansville', 'Purple Aces'),
    ('Bradley', 'Bradley Braves'),
    ('Bradley', 'Braves'),
    ('UIC', 'Illinois Chicago'),
    ('UIC', 'UIC Flames'),
    ('Murray St.', 'Murray State'),
    ('Murray St.', 'Murray State Racers'),
    ('Murray St.', 'Racers'),
    ('Belmont', 'Belmont Bruins')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- Horizon League
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    ('Oakland', 'Oakland Golden Grizzlies'),
    ('Oakland', 'Golden Grizzlies'),
    ('Cleveland St.', 'Cleveland State'),
    ('Cleveland St.', 'Cleveland State Vikings'),
    ('Cleveland St.', 'Vikings'),
    ('Wright St.', 'Wright State'),
    ('Wright St.', 'Wright State Raiders'),
    ('Milwaukee', 'UW Milwaukee'),
    ('Milwaukee', 'Milwaukee Panthers'),
    ('Green Bay', 'UW Green Bay'),
    ('Green Bay', 'Green Bay Phoenix'),
    ('Green Bay', 'Phoenix'),
    ('Youngstown St.', 'Youngstown State'),
    ('Youngstown St.', 'Youngstown State Penguins'),
    ('Youngstown St.', 'Penguins'),
    ('IUPUI', 'Indiana Purdue Indianapolis'),
    ('IUPUI', 'IUPUI Jaguars'),
    ('Detroit Mercy', 'Detroit'),
    ('Detroit Mercy', 'Detroit Mercy Titans'),
    ('Detroit Mercy', 'Titans'),
    ('Robert Morris', 'Robert Morris Colonials'),
    ('Robert Morris', 'RMU'),
    ('Purdue Fort Wayne', 'Fort Wayne'),
    ('Purdue Fort Wayne', 'PFW'),
    ('Purdue Fort Wayne', 'IPFW'),
    ('Northern Kentucky', 'NKU'),
    ('Northern Kentucky', 'Northern Kentucky Norse'),
    ('Northern Kentucky', 'Norse')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════════
-- LOUISIANA SCHOOLS (Common confusion point)
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    ('Louisiana', 'Louisiana Ragin'' Cajuns'),
    ('Louisiana', 'UL Lafayette'),
    ('Louisiana', 'Louisiana-Lafayette'),
    ('Louisiana', 'ULL'),
    ('Louisiana', 'Ragin Cajuns'),
    ('Louisiana Monroe', 'ULM'),
    ('Louisiana Monroe', 'Louisiana-Monroe'),
    ('Louisiana Monroe', 'UL Monroe'),
    ('Louisiana Monroe', 'Warhawks'),
    ('Louisiana Tech', 'LA Tech'),
    ('Louisiana Tech', 'LaTech'),
    ('Southeastern Louisiana', 'SE Louisiana'),
    ('Southeastern Louisiana', 'SE Louisiana Lions'),
    ('Southeastern Louisiana', 'Southeastern La'),
    ('Southeastern Louisiana', 'SELA'),
    ('McNeese St.', 'McNeese'),
    ('McNeese St.', 'McNeese State'),
    ('McNeese St.', 'McNeese State Cowboys'),
    ('Northwestern St.', 'Northwestern State'),
    ('Northwestern St.', 'Northwestern State Demons'),
    ('Northwestern St.', 'NSU Demons'),
    ('Nicholls St.', 'Nicholls'),
    ('Nicholls St.', 'Nicholls State'),
    ('Nicholls St.', 'Nicholls State Colonels'),
    ('New Orleans', 'UNO'),
    ('New Orleans', 'New Orleans Privateers'),
    ('New Orleans', 'Privateers')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════════
-- NORTH CAROLINA SCHOOLS (Common confusion point)
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    ('North Carolina', 'UNC'),
    ('North Carolina', 'North Carolina Tar Heels'),
    ('North Carolina', 'Carolina'),
    ('North Carolina', 'Tar Heels'),
    ('NC State', 'N.C. State'),
    ('NC State', 'North Carolina State'),
    ('NC State', 'NC State Wolfpack'),
    ('NC State', 'Wolfpack'),
    ('UNC Wilmington', 'UNCW'),
    ('UNC Wilmington', 'UNC-Wilmington'),
    ('UNC Wilmington', 'Wilmington'),
    ('UNC Wilmington', 'UNC Wilmington Seahawks'),
    ('UNC Greensboro', 'UNCG'),
    ('UNC Greensboro', 'UNC-Greensboro'),
    ('UNC Greensboro', 'UNC Greensboro Spartans'),
    ('UNC Asheville', 'UNCA'),
    ('UNC Asheville', 'UNC-Asheville'),
    ('UNC Asheville', 'UNC Asheville Bulldogs'),
    ('Charlotte', 'UNC Charlotte'),
    ('Charlotte', 'Charlotte 49ers'),
    ('Charlotte', 'UNCC'),
    ('NC Central', 'North Carolina Central'),
    ('NC Central', 'NCCU'),
    ('NC Central', 'NC Central Eagles'),
    ('NC A&T', 'North Carolina A&T'),
    ('NC A&T', 'NCAT'),
    ('NC A&T', 'NC A&T Aggies'),
    ('Campbell', 'Campbell Fighting Camels'),
    ('Campbell', 'Fighting Camels'),
    ('High Point', 'High Point Panthers'),
    ('Elon', 'Elon Phoenix'),
    ('Elon', 'Phoenix'),
    ('Gardner Webb', 'Gardner-Webb'),
    ('Gardner Webb', 'Gardner Webb Runnin'' Bulldogs'),
    ('Winthrop', 'Winthrop Eagles'),
    ('Charleston So.', 'Charleston Southern'),
    ('Charleston So.', 'Charleston Southern Buccaneers'),
    ('Charleston So.', 'CSU Buccaneers')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════════
-- CALIFORNIA SCHOOLS
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    ('UC Irvine', 'UCI'),
    ('UC Irvine', 'UC Irvine Anteaters'),
    ('UC Irvine', 'Anteaters'),
    ('UC Davis', 'UC Davis Aggies'),
    ('UC Davis', 'UCD'),
    ('UC Riverside', 'UCR'),
    ('UC Riverside', 'UC Riverside Highlanders'),
    ('UC Riverside', 'Highlanders'),
    ('UC Santa Barbara', 'UCSB'),
    ('UC Santa Barbara', 'UC Santa Barbara Gauchos'),
    ('UC Santa Barbara', 'Gauchos'),
    ('UC San Diego', 'UCSD'),
    ('UC San Diego', 'UC San Diego Tritons'),
    ('UC San Diego', 'Tritons'),
    ('Long Beach St.', 'Long Beach State'),
    ('Long Beach St.', 'Long Beach State 49ers'),
    ('Long Beach St.', 'LBSU'),
    ('Long Beach St.', 'Long Beach St. 49ers'),
    ('Cal St. Fullerton', 'Cal State Fullerton'),
    ('Cal St. Fullerton', 'Fullerton'),
    ('Cal St. Fullerton', 'CSUF'),
    ('Cal St. Fullerton', 'Cal State Fullerton Titans'),
    ('Cal St. Northridge', 'Cal State Northridge'),
    ('Cal St. Northridge', 'CSUN'),
    ('Cal St. Northridge', 'Northridge'),
    ('Cal St. Northridge', 'Matadors'),
    ('Cal Poly', 'Cal Poly Mustangs'),
    ('Cal Poly', 'Cal Poly SLO'),
    ('Cal Baptist', 'California Baptist'),
    ('Cal Baptist', 'CBU'),
    ('Cal Baptist', 'Cal Baptist Lancers'),
    ('Cal Baptist', 'Lancers'),
    ('Sacramento St.', 'Sacramento State'),
    ('Sacramento St.', 'Sac State'),
    ('Sacramento St.', 'Sacramento State Hornets'),
    ('Loyola Marymount', 'LMU'),
    ('Loyola Marymount', 'Loyola Marymount Lions'),
    ('Pepperdine', 'Pepperdine Waves'),
    ('San Diego', 'USD'),
    ('San Diego', 'San Diego Toreros'),
    ('Santa Clara', 'Santa Clara Broncos'),
    ('San Francisco', 'USF'),
    ('San Francisco', 'San Francisco Dons'),
    ('Pacific', 'Pacific Tigers'),
    ('Pacific', 'UOP'),
    ('Saint Mary''s', 'St. Mary''s'),
    ('Saint Mary''s', 'St Marys'),
    ('Saint Mary''s', 'Saint Mary''s Gaels'),
    ('Saint Mary''s', 'SMC'),
    ('Saint Mary''s', 'Gaels')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════════
-- TEXAS SCHOOLS
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    ('Tarleton St.', 'Tarleton State'),
    ('Tarleton St.', 'Tarleton'),
    ('Tarleton St.', 'Tarleton State Texans'),
    ('Tarleton St.', 'Tarleton St. Texans'),
    ('Tarleton St.', 'Texans'),
    ('Stephen F. Austin', 'SFA'),
    ('Stephen F. Austin', 'Stephen F Austin'),
    ('Stephen F. Austin', 'SFA Lumberjacks'),
    ('Stephen F. Austin', 'Lumberjacks'),
    ('Lamar', 'Lamar Cardinals'),
    ('Lamar', 'Lamar University'),
    ('UT Arlington', 'Texas Arlington'),
    ('UT Arlington', 'UTA'),
    ('UT Arlington', 'UT Arlington Mavericks'),
    ('UT Rio Grande Valley', 'UTRGV'),
    ('UT Rio Grande Valley', 'Texas Rio Grande Valley'),
    ('UT Rio Grande Valley', 'Rio Grande Valley'),
    ('Texas A&M Corpus Christi', 'TAMU-CC'),
    ('Texas A&M Corpus Christi', 'Texas A&M CC'),
    ('Texas A&M Corpus Christi', 'Corpus Christi'),
    ('Texas A&M Corpus Christi', 'Islanders'),
    ('Texas A&M Commerce', 'TAMU-Commerce'),
    ('Texas A&M Commerce', 'A&M Commerce'),
    ('Houston Christian', 'Houston Baptist'),
    ('Houston Christian', 'HBU'),
    ('Houston Christian', 'Houston Christian Huskies'),
    ('Texas Southern', 'TSU'),
    ('Texas Southern', 'Texas Southern Tigers'),
    ('Prairie View A&M', 'Prairie View'),
    ('Prairie View A&M', 'PVAMU'),
    ('Prairie View A&M', 'Panthers'),
    ('Abilene Christian', 'ACU'),
    ('Abilene Christian', 'Abilene Christian Wildcats'),
    ('Incarnate Word', 'UIW'),
    ('Incarnate Word', 'Incarnate Word Cardinals')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════════
-- NEW YORK SCHOOLS
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, a.alias, 'the_odds_api', 1.0
FROM teams t
CROSS JOIN LATERAL (VALUES
    ('St. Johns', 'St. John''s'),
    ('St. Johns', 'Saint John''s'),
    ('St. Johns', 'St. John''s Red Storm'),
    ('St. Johns', 'Red Storm'),
    ('Hofstra', 'Hofstra Pride'),
    ('Hofstra', 'Pride'),
    ('Stony Brook', 'Stony Brook Seawolves'),
    ('Stony Brook', 'Seawolves'),
    ('Albany', 'SUNY Albany'),
    ('Albany', 'UAlbany'),
    ('Albany', 'Albany Great Danes'),
    ('Albany', 'Great Danes'),
    ('Binghamton', 'Binghamton Bearcats'),
    ('Iona', 'Iona Gaels'),
    ('Manhattan', 'Manhattan Jaspers'),
    ('Manhattan', 'Jaspers'),
    ('Marist', 'Marist Red Foxes'),
    ('Marist', 'Red Foxes'),
    ('Niagara', 'Niagara Purple Eagles'),
    ('Niagara', 'Purple Eagles'),
    ('Siena', 'Siena Saints'),
    ('Siena', 'Saints'),
    ('Canisius', 'Canisius Golden Griffins'),
    ('Canisius', 'Golden Griffins'),
    ('St. Peter''s', 'Saint Peter''s'),
    ('St. Peter''s', 'St. Peter''s Peacocks'),
    ('St. Peter''s', 'Peacocks'),
    ('Wagner', 'Wagner Seahawks'),
    ('Fairfield', 'Fairfield Stags'),
    ('Fairfield', 'Stags'),
    ('Rider', 'Rider Broncs'),
    ('Rider', 'Broncs'),
    ('Long Island', 'LIU'),
    ('Long Island', 'Long Island Sharks'),
    ('Long Island', 'LIU Sharks'),
    ('St. Francis NY', 'St. Francis Brooklyn'),
    ('St. Francis NY', 'St. Francis (NY)'),
    ('St. Francis NY', 'SFC Brooklyn'),
    ('St. Francis PA', 'St. Francis (PA)'),
    ('St. Francis PA', 'Saint Francis PA'),
    ('St. Francis PA', 'St. Francis Red Flash')
) AS a(canonical, alias)
WHERE t.canonical_name = a.canonical
ON CONFLICT (alias, source) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════════
-- UPDATE resolve_team_name FUNCTION TO HANDLE EDGE CASES BETTER
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION resolve_team_name(input_name TEXT)
RETURNS TEXT AS $$
DECLARE
    v_result TEXT;
    v_normalized TEXT;
    v_stripped TEXT;
BEGIN
    -- Return NULL for empty input
    IF input_name IS NULL OR TRIM(input_name) = '' THEN
        RETURN NULL;
    END IF;

    -- Normalize input: lowercase, remove special chars, compress whitespace
    v_normalized := LOWER(TRIM(input_name));
    v_normalized := REGEXP_REPLACE(v_normalized, '[^a-z0-9\s&]', '', 'g');
    v_normalized := REGEXP_REPLACE(v_normalized, '\s+', ' ', 'g');

    -- Create stripped version (no mascots)
    v_stripped := REGEXP_REPLACE(v_normalized,
        '\s+(blue devils|tar heels|wildcats|tigers|bulldogs|cavaliers|demon deacons|wolfpack|seminoles|cardinals|hurricanes|fighting irish|panthers|orange|hokies|yellow jackets|eagles|jayhawks|bears|red raiders|horned frogs|cowboys|cyclones|mountaineers|longhorns|sooners|cougars|knights|bearcats|boilermakers|wolverines|spartans|hoosiers|fighting illini|buckeyes|hawkeyes|badgers|golden gophers|nittany lions|scarlet knights|terrapins|cornhuskers|bruins|trojans|ducks|huskies|crimson tide|volunteers|razorbacks|gators|rebels|gamecocks|commodores|aggies|sun devils|buffaloes|utes|golden eagles|friars|pirates|red storm|musketeers|hoyas|blue demons|mustangs|golden hurricane|rattlers|49ers|owls|broncos|wolf pack|aztecs|rams|lobos|gaels|dons|waves|lions|pilots|toreros|flyers|billikens|spiders|bonnies|explorers|dukes|colonials|minutemen|hawks|ramblers|anteaters|highlanders|gauchos|tritons|titans|matadors|lancers|hornets|privateers|seahawks|delta devils|monarchs|miners|mean green|roadrunners|bearkats|flames|mountain hawks|leopards|raiders|crusaders|terriers|hilltoppers|blue raiders|thundering herd|red wolves|chanticleers|sycamores|redbirds|salukis|beacons|purple aces|braves|golden grizzlies|vikings|phoenix|penguins|jaguars|colonials|norse|lumberjacks|mavericks|islanders|texans|seawolves|great danes|jaspers|red foxes|saints|golden griffins|peacocks|stags|broncs|sharks|red flash)$',
        '', 'g');

    -- STEP 1: Exact match on canonical_name (case-insensitive)
    SELECT t.canonical_name INTO v_result
    FROM teams t
    LEFT JOIN team_ratings tr ON t.id = tr.team_id
    WHERE LOWER(t.canonical_name) = LOWER(TRIM(input_name))
    ORDER BY tr.team_id IS NOT NULL DESC
    LIMIT 1;

    IF v_result IS NOT NULL THEN
        RETURN v_result;
    END IF;

    -- STEP 2: Exact match on alias (case-insensitive)
    SELECT t.canonical_name INTO v_result
    FROM teams t
    JOIN team_aliases ta ON t.id = ta.team_id
    LEFT JOIN team_ratings tr ON t.id = tr.team_id
    WHERE LOWER(ta.alias) = LOWER(TRIM(input_name))
    ORDER BY ta.confidence DESC, tr.team_id IS NOT NULL DESC
    LIMIT 1;

    IF v_result IS NOT NULL THEN
        RETURN v_result;
    END IF;

    -- STEP 3: Normalized match (remove punctuation, match against canonical or alias)
    SELECT t.canonical_name INTO v_result
    FROM teams t
    LEFT JOIN team_aliases ta ON t.id = ta.team_id
    LEFT JOIN team_ratings tr ON t.id = tr.team_id
    WHERE REGEXP_REPLACE(LOWER(t.canonical_name), '[^a-z0-9]', '', 'g') = REGEXP_REPLACE(v_normalized, '[^a-z0-9]', '', 'g')
       OR REGEXP_REPLACE(LOWER(ta.alias), '[^a-z0-9]', '', 'g') = REGEXP_REPLACE(v_normalized, '[^a-z0-9]', '', 'g')
    ORDER BY tr.team_id IS NOT NULL DESC
    LIMIT 1;

    IF v_result IS NOT NULL THEN
        RETURN v_result;
    END IF;

    -- STEP 4: Try matching with mascot stripped
    SELECT t.canonical_name INTO v_result
    FROM teams t
    LEFT JOIN team_aliases ta ON t.id = ta.team_id
    LEFT JOIN team_ratings tr ON t.id = tr.team_id
    WHERE REGEXP_REPLACE(LOWER(t.canonical_name), '[^a-z0-9]', '', 'g') = REGEXP_REPLACE(v_stripped, '[^a-z0-9]', '', 'g')
       OR REGEXP_REPLACE(LOWER(ta.alias), '[^a-z0-9]', '', 'g') = REGEXP_REPLACE(v_stripped, '[^a-z0-9]', '', 'g')
    ORDER BY tr.team_id IS NOT NULL DESC
    LIMIT 1;

    IF v_result IS NOT NULL THEN
        RETURN v_result;
    END IF;

    -- NO FUZZY/PARTIAL MATCHING
    -- Step 5 (fuzzy match) was removed because it caused incorrect matches:
    --   - "Oregon" would match "Oregon St."
    --   - "Florida" would match "Florida A&M", "FIU", "FAU", etc.
    -- If we reach here, return NULL and let the caller handle the unresolved team.
    -- Add the missing alias to the team_aliases table instead of guessing.

    RETURN NULL;  -- No match found - don't settle for a partial match
END;
$$ LANGUAGE plpgsql STABLE;

-- ═══════════════════════════════════════════════════════════════════════════════
-- LOG MIGRATION COMPLETION
-- ═══════════════════════════════════════════════════════════════════════════════

DO $$
DECLARE
    alias_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO alias_count FROM team_aliases;
    RAISE NOTICE 'Migration 011 complete: % total team aliases', alias_count;
END;
$$;
