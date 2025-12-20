-- Seed Data for NCAAF v5.0 Teams
-- Major FBS Teams with historical data
-- Run with: psql -U ncaaf_user -d ncaaf_v5 -f scripts/seed_teams.sql

BEGIN;

-- Clear existing data (use with caution in production!)
-- TRUNCATE teams CASCADE;

-- Power 5 Conference Teams (SEC)
INSERT INTO teams (team_id, team_code, school_name, mascot, conference, division, talent_composite) VALUES
(1, 'ALA', 'Alabama', 'Crimson Tide', 'SEC', 'FBS', 95.8),
(2, 'GA', 'Georgia', 'Bulldogs', 'SEC', 'FBS', 94.5),
(3, 'LSU', 'LSU', 'Tigers', 'SEC', 'FBS', 91.2),
(4, 'MISS', 'Ole Miss', 'Rebels', 'SEC', 'FBS', 88.9),
(5, 'TENN', 'Tennessee', 'Volunteers', 'SEC', 'FBS', 89.3),
(6, 'FLA', 'Florida', 'Gators', 'SEC', 'FBS', 87.6),
(7, 'MSST', 'Mississippi State', 'Bulldogs', 'SEC', 'FBS', 82.1),
(8, 'ARK', 'Arkansas', 'Razorbacks', 'SEC', 'FBS', 83.4),
(9, 'AUB', 'Auburn', 'Tigers', 'SEC', 'FBS', 86.7),
(10, 'SCAR', 'South Carolina', 'Gamecocks', 'SEC', 'FBS', 82.8),
(11, 'MIZ', 'Missouri', 'Tigers', 'SEC', 'FBS', 83.9),
(12, 'TAMU', 'Texas A&M', 'Aggies', 'SEC', 'FBS', 90.1),
(13, 'UK', 'Kentucky', 'Wildcats', 'SEC', 'FBS', 80.5),
(14, 'VAN', 'Vanderbilt', 'Commodores', 'SEC', 'FBS', 75.2)
ON CONFLICT (team_id) DO UPDATE SET
  school_name = EXCLUDED.school_name,
  mascot = EXCLUDED.mascot,
  conference = EXCLUDED.conference,
  talent_composite = EXCLUDED.talent_composite;

-- Power 5 Conference Teams (Big Ten)
INSERT INTO teams (team_id, team_code, school_name, mascot, conference, division, talent_composite) VALUES
(20, 'OSU', 'Ohio State', 'Buckeyes', 'Big Ten', 'FBS', 95.3),
(21, 'MICH', 'Michigan', 'Wolverines', 'Big Ten', 'FBS', 93.7),
(22, 'PSU', 'Penn State', 'Nittany Lions', 'Big Ten', 'FBS', 90.8),
(23, 'WISC', 'Wisconsin', 'Badgers', 'Big Ten', 'FBS', 85.4),
(24, 'IOWA', 'Iowa', 'Hawkeyes', 'Big Ten', 'FBS', 82.9),
(25, 'MSU', 'Michigan State', 'Spartans', 'Big Ten', 'FBS', 81.3),
(26, 'MINN', 'Minnesota', 'Golden Gophers', 'Big Ten', 'FBS', 79.6),
(27, 'NEB', 'Nebraska', 'Cornhuskers', 'Big Ten', 'FBS', 83.2),
(28, 'ILL', 'Illinois', 'Fighting Illini', 'Big Ten', 'FBS', 77.8),
(29, 'IND', 'Indiana', 'Hoosiers', 'Big Ten', 'FBS', 76.5),
(30, 'PUR', 'Purdue', 'Boilermakers', 'Big Ten', 'FBS', 75.9),
(31, 'NW', 'Northwestern', 'Wildcats', 'Big Ten', 'FBS', 74.3),
(32, 'MD', 'Maryland', 'Terrapins', 'Big Ten', 'FBS', 78.4),
(33, 'RUT', 'Rutgers', 'Scarlet Knights', 'Big Ten', 'FBS', 73.7)
ON CONFLICT (team_id) DO UPDATE SET
  school_name = EXCLUDED.school_name,
  mascot = EXCLUDED.mascot,
  conference = EXCLUDED.conference,
  talent_composite = EXCLUDED.talent_composite;

-- Power 5 Conference Teams (ACC)
INSERT INTO teams (team_id, team_code, school_name, mascot, conference, division, talent_composite) VALUES
(40, 'CLEM', 'Clemson', 'Tigers', 'ACC', 'FBS', 92.6),
(41, 'FSU', 'Florida State', 'Seminoles', 'ACC', 'FBS', 89.7),
(42, 'MIAMI', 'Miami', 'Hurricanes', 'ACC', 'FBS', 88.5),
(43, 'UNC', 'North Carolina', 'Tar Heels', 'ACC', 'FBS', 84.2),
(44, 'NCST', 'NC State', 'Wolfpack', 'ACC', 'FBS', 82.3),
(45, 'VT', 'Virginia Tech', 'Hokies', 'ACC', 'FBS', 81.7),
(46, 'PITT', 'Pittsburgh', 'Panthers', 'ACC', 'FBS', 80.9),
(47, 'LOU', 'Louisville', 'Cardinals', 'ACC', 'FBS', 81.4),
(48, 'UVA', 'Virginia', 'Cavaliers', 'ACC', 'FBS', 77.6),
(49, 'GT', 'Georgia Tech', 'Yellow Jackets', 'ACC', 'FBS', 76.8),
(50, 'BC', 'Boston College', 'Eagles', 'ACC', 'FBS', 75.4),
(51, 'SYR', 'Syracuse', 'Orange', 'ACC', 'FBS', 74.9),
(52, 'WAKE', 'Wake Forest', 'Demon Deacons', 'ACC', 'FBS', 76.2),
(53, 'DUKE', 'Duke', 'Blue Devils', 'ACC', 'FBS', 72.1)
ON CONFLICT (team_id) DO UPDATE SET
  school_name = EXCLUDED.school_name,
  mascot = EXCLUDED.mascot,
  conference = EXCLUDED.conference,
  talent_composite = EXCLUDED.talent_composite;

-- Power 5 Conference Teams (Big 12)
INSERT INTO teams (team_id, team_code, school_name, mascot, conference, division, talent_composite) VALUES
(60, 'TEX', 'Texas', 'Longhorns', 'Big 12', 'FBS', 93.4),
(61, 'OU', 'Oklahoma', 'Sooners', 'Big 12', 'FBS', 91.8),
(62, 'OKST', 'Oklahoma State', 'Cowboys', 'Big 12', 'FBS', 85.6),
(63, 'TCU', 'TCU', 'Horned Frogs', 'Big 12', 'FBS', 84.3),
(64, 'BAY', 'Baylor', 'Bears', 'Big 12', 'FBS', 83.7),
(65, 'TTU', 'Texas Tech', 'Red Raiders', 'Big 12', 'FBS', 81.2),
(66, 'KSU', 'Kansas State', 'Wildcats', 'Big 12', 'FBS', 80.8),
(67, 'ISU', 'Iowa State', 'Cyclones', 'Big 12', 'FBS', 79.4),
(68, 'WVU', 'West Virginia', 'Mountaineers', 'Big 12', 'FBS', 78.9),
(69, 'KU', 'Kansas', 'Jayhawks', 'Big 12', 'FBS', 72.6)
ON CONFLICT (team_id) DO UPDATE SET
  school_name = EXCLUDED.school_name,
  mascot = EXCLUDED.mascot,
  conference = EXCLUDED.conference,
  talent_composite = EXCLUDED.talent_composite;

-- Power 5 Conference Teams (Pac-12)
INSERT INTO teams (team_id, team_code, school_name, mascot, conference, division, talent_composite) VALUES
(80, 'USC', 'USC', 'Trojans', 'Pac-12', 'FBS', 92.1),
(81, 'WASH', 'Washington', 'Huskies', 'Pac-12', 'FBS', 88.9),
(82, 'ORE', 'Oregon', 'Ducks', 'Pac-12', 'FBS', 91.3),
(83, 'UCLA', 'UCLA', 'Bruins', 'Pac-12', 'FBS', 86.7),
(84, 'STAN', 'Stanford', 'Cardinal', 'Pac-12', 'FBS', 82.4),
(85, 'CAL', 'California', 'Golden Bears', 'Pac-12', 'FBS', 78.3),
(86, 'UTAH', 'Utah', 'Utes', 'Pac-12', 'FBS', 87.2),
(87, 'ARIZ', 'Arizona', 'Wildcats', 'Pac-12', 'FBS', 79.1),
(88, 'ASU', 'Arizona State', 'Sun Devils', 'Pac-12', 'FBS', 80.5),
(89, 'ORE ST', 'Oregon State', 'Beavers', 'Pac-12', 'FBS', 75.6),
(90, 'WASH ST', 'Washington State', 'Cougars', 'Pac-12', 'FBS', 76.8),
(91, 'COLO', 'Colorado', 'Buffaloes', 'Pac-12', 'FBS', 77.4)
ON CONFLICT (team_id) DO UPDATE SET
  school_name = EXCLUDED.school_name,
  mascot = EXCLUDED.mascot,
  conference = EXCLUDED.conference,
  talent_composite = EXCLUDED.talent_composite;

-- Group of 5 - Notable Teams (AAC, Conference USA, MAC, Mountain West, Sun Belt)
INSERT INTO teams (team_id, team_code, school_name, mascot, conference, division, talent_composite) VALUES
(100, 'CIN', 'Cincinnati', 'Bearcats', 'AAC', 'FBS', 84.1),
(101, 'UCF', 'UCF', 'Knights', 'AAC', 'FBS', 82.7),
(102, 'HOU', 'Houston', 'Cougars', 'AAC', 'FBS', 83.2),
(103, 'MEM', 'Memphis', 'Tigers', 'AAC', 'FBS', 79.8),
(104, 'SMU', 'SMU', 'Mustangs', 'AAC', 'FBS', 80.3),
(105, 'BSU', 'Boise State', 'Broncos', 'Mountain West', 'FBS', 78.9),
(106, 'SDSU', 'San Diego State', 'Aztecs', 'Mountain West', 'FBS', 76.4),
(107, 'AFA', 'Air Force', 'Falcons', 'Mountain West', 'FBS', 74.2),
(108, 'NAVY', 'Navy', 'Midshipmen', 'AAC', 'FBS', 75.8),
(109, 'ARMY', 'Army', 'Black Knights', 'Independent', 'FBS', 73.9),
(110, 'ND', 'Notre Dame', 'Fighting Irish', 'Independent', 'FBS', 94.2),
(111, 'BYU', 'BYU', 'Cougars', 'Independent', 'FBS', 82.6)
ON CONFLICT (team_id) DO UPDATE SET
  school_name = EXCLUDED.school_name,
  mascot = EXCLUDED.mascot,
  conference = EXCLUDED.conference,
  talent_composite = EXCLUDED.talent_composite;

COMMIT;

-- Verify insertion
SELECT COUNT(*) AS total_teams FROM teams;
SELECT conference, COUNT(*) AS team_count FROM teams GROUP BY conference ORDER BY team_count DESC;

ANALYZE teams;
