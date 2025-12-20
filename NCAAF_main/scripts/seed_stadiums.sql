-- Seed Data for NCAAF v5.0 Stadiums
-- Major FBS Stadiums
-- Run with: psql -U ncaaf_user -d ncaaf_v5 -f scripts/seed_stadiums.sql

BEGIN;

-- Major SEC Stadiums
INSERT INTO stadiums (stadium_id, name, city, state, capacity, field_type, elevation) VALUES
(1, 'Bryant-Denny Stadium', 'Tuscaloosa', 'AL', 101821, 'Grass', 229),
(2, 'Sanford Stadium', 'Athens', 'GA', 92746, 'Grass', 584),
(3, 'Tiger Stadium', 'Baton Rouge', 'LA', 102321, 'Grass', 56),
(4, 'Vaught-Hemingway Stadium', 'Oxford', 'MS', 64038, 'Grass', 328),
(5, 'Neyland Stadium', 'Knoxville', 'TN', 101915, 'Grass', 896),
(6, 'Ben Hill Griffin Stadium', 'Gainesville', 'FL', 88548, 'Grass', 150),
(7, 'Davis Wade Stadium', 'Starkville', 'MS', 61337, 'Grass', 295),
(8, 'Donald W. Reynolds Razorback Stadium', 'Fayetteville', 'AR', 76412, 'Grass', 1287),
(9, 'Jordan-Hare Stadium', 'Auburn', 'AL', 87451, 'Grass', 709),
(10, 'Williams-Brice Stadium', 'Columbia', 'SC', 77559, 'Grass', 285),
(11, 'Faurot Field', 'Columbia', 'MO', 62621, 'Grass', 764),
(12, 'Kyle Field', 'College Station', 'TX', 102733, 'Grass', 367),
(13, 'Kroger Field', 'Lexington', 'KY', 61000, 'Grass', 965),
(14, 'Vanderbilt Stadium', 'Nashville', 'TN', 40550, 'Grass', 597)
ON CONFLICT (stadium_id) DO UPDATE SET
  name = EXCLUDED.name,
  capacity = EXCLUDED.capacity,
  field_type = EXCLUDED.field_type;

-- Major Big Ten Stadiums
INSERT INTO stadiums (stadium_id, name, city, state, capacity, field_type, elevation) VALUES
(20, 'Ohio Stadium', 'Columbus', 'OH', 102780, 'Grass', 761),
(21, 'Michigan Stadium', 'Ann Arbor', 'MI', 107601, 'Grass', 881),
(22, 'Beaver Stadium', 'State College', 'PA', 106572, 'Grass', 1175),
(23, 'Camp Randall Stadium', 'Madison', 'WI', 80321, 'Grass', 873),
(24, 'Kinnick Stadium', 'Iowa City', 'IA', 69250, 'Grass', 669),
(25, 'Spartan Stadium', 'East Lansing', 'MI', 75005, 'Grass', 857),
(26, 'Huntington Bank Stadium', 'Minneapolis', 'MN', 50805, 'Turf', 838),
(27, 'Memorial Stadium', 'Lincoln', 'NE', 85458, 'Turf', 1204),
(28, 'Memorial Stadium', 'Champaign', 'IL', 60670, 'Turf', 725),
(29, 'Memorial Stadium', 'Bloomington', 'IN', 52929, 'Turf', 779),
(30, 'Ross-Ade Stadium', 'West Lafayette', 'IN', 57236, 'Grass', 620),
(31, 'Ryan Field', 'Evanston', 'IL', 47130, 'Grass', 594),
(32, 'SECU Stadium', 'College Park', 'MD', 51802, 'Grass', 213),
(33, 'SHI Stadium', 'Piscataway', 'NJ', 52454, 'Turf', 95)
ON CONFLICT (stadium_id) DO UPDATE SET
  name = EXCLUDED.name,
  capacity = EXCLUDED.capacity,
  field_type = EXCLUDED.field_type;

-- Major ACC Stadiums
INSERT INTO stadiums (stadium_id, name, city, state, capacity, field_type, elevation) VALUES
(40, 'Memorial Stadium', 'Clemson', 'SC', 81500, 'Grass', 709),
(41, 'Doak Campbell Stadium', 'Tallahassee', 'FL', 79560, 'Grass', 68),
(42, 'Hard Rock Stadium', 'Miami Gardens', 'FL', 65326, 'Grass', 7),
(43, 'Kenan Memorial Stadium', 'Chapel Hill', 'NC', 50500, 'Turf', 489),
(44, 'Carter-Finley Stadium', 'Raleigh', 'NC', 57583, 'Grass', 354),
(45, 'Lane Stadium', 'Blacksburg', 'VA', 65632, 'Grass', 2057),
(46, 'Acrisure Stadium', 'Pittsburgh', 'PA', 68400, 'Grass', 761),
(47, 'Cardinal Stadium', 'Louisville', 'KY', 65000, 'Turf', 456),
(48, 'Scott Stadium', 'Charlottesville', 'VA', 61500, 'Turf', 260),
(49, 'Bobby Dodd Stadium', 'Atlanta', 'GA', 55000, 'Turf', 1050),
(50, 'Alumni Stadium', 'Chestnut Hill', 'MA', 44500, 'Turf', 141),
(51, 'JMA Wireless Dome', 'Syracuse', 'NY', 49262, 'Turf', 407),
(52, 'Truist Field', 'Winston-Salem', 'NC', 31500, 'Grass', 912),
(53, 'Wallace Wade Stadium', 'Durham', 'NC', 40004, 'Grass', 404)
ON CONFLICT (stadium_id) DO UPDATE SET
  name = EXCLUDED.name,
  capacity = EXCLUDED.capacity,
  field_type = EXCLUDED.field_type;

-- Major Big 12 Stadiums
INSERT INTO stadiums (stadium_id, name, city, state, capacity, field_type, elevation) VALUES
(60, 'Darrell K Royal-Texas Memorial Stadium', 'Austin', 'TX', 100119, 'Grass', 541),
(61, 'Gaylord Family Oklahoma Memorial Stadium', 'Norman', 'OK', 86112, 'Grass', 1175),
(62, 'Boone Pickens Stadium', 'Stillwater', 'OK', 60218, 'Grass', 909),
(63, 'Amon G. Carter Stadium', 'Fort Worth', 'TX', 47000, 'Grass', 650),
(64, 'McLane Stadium', 'Waco', 'TX', 45140, 'Grass', 469),
(65, 'Jones AT&T Stadium', 'Lubbock', 'TX', 60454, 'Turf', 3254),
(66, 'Bill Snyder Family Stadium', 'Manhattan', 'KS', 50000, 'Turf', 1027),
(67, 'Jack Trice Stadium', 'Ames', 'IA', 61500, 'Grass', 994),
(68, 'Mountaineer Field', 'Morgantown', 'WV', 60000, 'Turf', 1266),
(69, 'David Booth Kansas Memorial Stadium', 'Lawrence', 'KS', 47233, 'Turf', 912)
ON CONFLICT (stadium_id) DO UPDATE SET
  name = EXCLUDED.name,
  capacity = EXCLUDED.capacity,
  field_type = EXCLUDED.field_type;

-- Major Pac-12 Stadiums
INSERT INTO stadiums (stadium_id, name, city, state, capacity, field_type, elevation) VALUES
(80, 'Los Angeles Memorial Coliseum', 'Los Angeles', 'CA', 77500, 'Grass', 180),
(81, 'Husky Stadium', 'Seattle', 'WA', 70138, 'Turf', 30),
(82, 'Autzen Stadium', 'Eugene', 'OR', 54000, 'Turf', 374),
(83, 'Rose Bowl', 'Pasadena', 'CA', 88565, 'Grass', 850),
(84, 'Stanford Stadium', 'Stanford', 'CA', 50424, 'Grass', 30),
(85, 'California Memorial Stadium', 'Berkeley', 'CA', 63000, 'Turf', 330),
(86, 'Rice-Eccles Stadium', 'Salt Lake City', 'UT', 51444, 'Grass', 4657),
(87, 'Arizona Stadium', 'Tucson', 'AZ', 50782, 'Grass', 2400),
(88, 'Sun Devil Stadium', 'Tempe', 'AZ', 53599, 'Grass', 1160),
(89, 'Reser Stadium', 'Corvallis', 'OR', 26407, 'Turf', 222),
(90, 'Martin Stadium', 'Pullman', 'WA', 32952, 'Turf', 2555),
(91, 'Folsom Field', 'Boulder', 'CO', 50183, 'Grass', 5430)
ON CONFLICT (stadium_id) DO UPDATE SET
  name = EXCLUDED.name,
  capacity = EXCLUDED.capacity,
  field_type = EXCLUDED.field_type;

-- Notable Independent/Group of 5 Stadiums
INSERT INTO stadiums (stadium_id, name, city, state, capacity, field_type, elevation) VALUES
(110, 'Notre Dame Stadium', 'South Bend', 'IN', 77622, 'Grass', 695),
(111, 'LaVell Edwards Stadium', 'Provo', 'UT', 63470, 'Grass', 4658),
(100, 'Nippert Stadium', 'Cincinnati', 'OH', 40000, 'Turf', 509),
(101, 'FBC Mortgage Stadium', 'Orlando', 'FL', 44206, 'Grass', 53),
(102, 'TDECU Stadium', 'Houston', 'TX', 40000, 'Turf', 49),
(103, 'Liberty Bowl Memorial Stadium', 'Memphis', 'TN', 58318, 'Turf', 299),
(105, 'Albertsons Stadium', 'Boise', 'ID', 36387, 'Turf', 2838),
(106, 'Snapdragon Stadium', 'San Diego', 'CA', 35000, 'Grass', 541),
(108, 'Navy-Marine Corps Memorial Stadium', 'Annapolis', 'MD', 34000, 'Turf', 10),
(109, 'Michie Stadium', 'West Point', 'NY', 38000, 'Turf', 335)
ON CONFLICT (stadium_id) DO UPDATE SET
  name = EXCLUDED.name,
  capacity = EXCLUDED.capacity,
  field_type = EXCLUDED.field_type;

COMMIT;

-- Verify insertion
SELECT COUNT(*) AS total_stadiums FROM stadiums;
SELECT field_type, COUNT(*) AS stadium_count FROM stadiums GROUP BY field_type;
SELECT state, COUNT(*) AS stadium_count FROM stadiums GROUP BY state ORDER BY stadium_count DESC LIMIT 10;

ANALYZE stadiums;
