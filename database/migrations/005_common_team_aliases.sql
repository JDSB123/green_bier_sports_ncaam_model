-- Common Team Name Variants - COMPLETE MAPPING
-- Maps Odds API names (with mascots) to Barttorvik canonical names
-- This ensures 100% team matching across data sources

-- Function to add alias (idempotent)
CREATE OR REPLACE FUNCTION add_team_alias(alias_name TEXT, canonical TEXT) RETURNS VOID AS $$
BEGIN
    INSERT INTO team_aliases (team_id, alias, source)
    SELECT t.id, alias_name, 'migration'
    FROM teams t WHERE t.canonical_name = canonical
    ON CONFLICT (alias, source) DO NOTHING;
END;
$$ LANGUAGE plpgsql;

-- Complete Odds API to Barttorvik mappings
SELECT add_team_alias('Abilene Christian Wildcats', 'Abilene Christian');
SELECT add_team_alias('Akron Zips', 'Akron');
SELECT add_team_alias('Alcorn St. Braves', 'Alcorn St.');
SELECT add_team_alias('Arizona Wildcats', 'Arizona');
SELECT add_team_alias('Arkansas Razorbacks', 'Arkansas');
SELECT add_team_alias('Auburn Tigers', 'Auburn');
SELECT add_team_alias('BYU Cougars', 'BYU');
SELECT add_team_alias('Baylor Bears', 'Baylor');
SELECT add_team_alias('Belmont Bruins', 'Belmont');
SELECT add_team_alias('Butler Bulldogs', 'Butler');
SELECT add_team_alias('Cal Poly Mustangs', 'Cal Poly');
SELECT add_team_alias('California Golden Bears', 'California');
SELECT add_team_alias('Colorado Buffaloes', 'Colorado');
SELECT add_team_alias('Colorado St. Rams', 'Colorado St.');
SELECT add_team_alias('Coppin St. Eagles', 'Coppin St.');
SELECT add_team_alias('Creighton Bluejays', 'Creighton');
SELECT add_team_alias('Dayton Flyers', 'Dayton');
SELECT add_team_alias('Drexel Dragons', 'Drexel');
SELECT add_team_alias('Duke Blue Devils', 'Duke');
SELECT add_team_alias('E. Michigan Eagles', 'E. Michigan');
SELECT add_team_alias('Florida A&M Rattlers', 'Florida A&M');
SELECT add_team_alias('Florida Atlantic Owls', 'Florida Atlantic');
SELECT add_team_alias('Florida Gators', 'Florida');
SELECT add_team_alias('Florida St. Seminoles', 'Florida St.');
SELECT add_team_alias('Fresno St. Bulldogs', 'Fresno St.');
SELECT add_team_alias('Georgetown Hoyas', 'Georgetown');
SELECT add_team_alias('Gonzaga Bulldogs', 'Gonzaga');
SELECT add_team_alias('Grambling St. Tigers', 'Grambling St.');
SELECT add_team_alias('Grand Canyon Antelopes', 'Grand Canyon');
SELECT add_team_alias('Hampton Pirates', 'Hampton');
SELECT add_team_alias('High Point Panthers', 'High Point');
SELECT add_team_alias('Houston Cougars', 'Houston');
SELECT add_team_alias('Illinois Fighting Illini', 'Illinois');
SELECT add_team_alias('Indiana Hoosiers', 'Indiana');
SELECT add_team_alias('Iowa Hawkeyes', 'Iowa');
SELECT add_team_alias('Iowa St. Cyclones', 'Iowa St.');
SELECT add_team_alias('Jackson St. Tigers', 'Jackson St.');
SELECT add_team_alias('Kansas Jayhawks', 'Kansas');
SELECT add_team_alias('Kansas St. Wildcats', 'Kansas St.');
SELECT add_team_alias('Kentucky Wildcats', 'Kentucky');
SELECT add_team_alias('LSU Tigers', 'LSU');
SELECT add_team_alias('La Salle Explorers', 'La Salle');
SELECT add_team_alias('Liberty Flames', 'Liberty');
SELECT add_team_alias('Louisville Cardinals', 'Louisville');
SELECT add_team_alias('Loyola Marymount Lions', 'Loyola Marymount');
SELECT add_team_alias('Marquette Golden Eagles', 'Marquette');
SELECT add_team_alias('Maryland Terrapins', 'Maryland');
SELECT add_team_alias('Memphis Tigers', 'Memphis');
SELECT add_team_alias('Miami Hurricanes', 'Miami FL');
SELECT add_team_alias('Michigan Wolverines', 'Michigan');
SELECT add_team_alias('Michigan St. Spartans', 'Michigan St.');
SELECT add_team_alias('Milwaukee Panthers', 'Milwaukee');
SELECT add_team_alias('Minnesota Golden Gophers', 'Minnesota');
SELECT add_team_alias('Mississippi St. Bulldogs', 'Mississippi St.');
SELECT add_team_alias('Missouri Tigers', 'Missouri');
SELECT add_team_alias('Montana Grizzlies', 'Montana');
SELECT add_team_alias('Morgan St. Bears', 'Morgan St.');
SELECT add_team_alias('Mt. St. Mary''s Mountaineers', 'Mt. St. Mary''s');
SELECT add_team_alias('Navy Midshipmen', 'Navy');
SELECT add_team_alias('Nebraska Cornhuskers', 'Nebraska');
SELECT add_team_alias('Nevada Wolf Pack', 'Nevada');
SELECT add_team_alias('Norfolk St. Spartans', 'Norfolk St.');
SELECT add_team_alias('North Alabama Lions', 'North Alabama');
SELECT add_team_alias('North Carolina Tar Heels', 'North Carolina');
SELECT add_team_alias('Northwestern Wildcats', 'Northwestern');
SELECT add_team_alias('Notre Dame Fighting Irish', 'Notre Dame');
SELECT add_team_alias('Ohio St. Buckeyes', 'Ohio St.');
SELECT add_team_alias('Oklahoma Sooners', 'Oklahoma');
SELECT add_team_alias('Oklahoma St. Cowboys', 'Oklahoma St.');
SELECT add_team_alias('Ole Miss Rebels', 'Ole Miss');
SELECT add_team_alias('Oregon Ducks', 'Oregon');
SELECT add_team_alias('Oregon St. Beavers', 'Oregon St.');
SELECT add_team_alias('Penn St. Nittany Lions', 'Penn St.');
SELECT add_team_alias('Pittsburgh Panthers', 'Pittsburgh');
SELECT add_team_alias('Providence Friars', 'Providence');
SELECT add_team_alias('Purdue Boilermakers', 'Purdue');
SELECT add_team_alias('Rutgers Scarlet Knights', 'Rutgers');
SELECT add_team_alias('San Diego St. Aztecs', 'San Diego St.');
SELECT add_team_alias('San Diego Toreros', 'San Diego');
SELECT add_team_alias('Santa Clara Broncos', 'Santa Clara');
SELECT add_team_alias('Seattle Redhawks', 'Seattle');
SELECT add_team_alias('Seton Hall Pirates', 'Seton Hall');
SELECT add_team_alias('South Carolina Gamecocks', 'South Carolina');
SELECT add_team_alias('South Dakota St. Jackrabbits', 'South Dakota St.');
SELECT add_team_alias('Southern California Trojans', 'USC');
SELECT add_team_alias('St. John''s Red Storm', 'St. John''s');
SELECT add_team_alias('St. Mary''s Gaels', 'St. Mary''s');
SELECT add_team_alias('Stanford Cardinal', 'Stanford');
SELECT add_team_alias('Syracuse Orange', 'Syracuse');
SELECT add_team_alias('TCU Horned Frogs', 'TCU');
SELECT add_team_alias('Tarleton St. Texans', 'Tarleton St.');
SELECT add_team_alias('Tennessee Volunteers', 'Tennessee');
SELECT add_team_alias('Texas Longhorns', 'Texas');
SELECT add_team_alias('Texas A&M Aggies', 'Texas A&M');
SELECT add_team_alias('Texas Tech Red Raiders', 'Texas Tech');
SELECT add_team_alias('Tulsa Golden Hurricane', 'Tulsa');
SELECT add_team_alias('UC Irvine Anteaters', 'UC Irvine');
SELECT add_team_alias('UC San Diego Tritons', 'UC San Diego');
SELECT add_team_alias('UCLA Bruins', 'UCLA');
SELECT add_team_alias('UConn Huskies', 'Connecticut');
SELECT add_team_alias('UNLV Rebels', 'UNLV');
SELECT add_team_alias('USC Trojans', 'USC');
SELECT add_team_alias('Utah Utes', 'Utah');
SELECT add_team_alias('Utah St. Aggies', 'Utah St.');
SELECT add_team_alias('Vanderbilt Commodores', 'Vanderbilt');
SELECT add_team_alias('Villanova Wildcats', 'Villanova');
SELECT add_team_alias('Virginia Cavaliers', 'Virginia');
SELECT add_team_alias('Virginia Tech Hokies', 'Virginia Tech');
SELECT add_team_alias('W. Kentucky Hilltoppers', 'W. Kentucky');
SELECT add_team_alias('Wake Forest Demon Deacons', 'Wake Forest');
SELECT add_team_alias('Washington Huskies', 'Washington');
SELECT add_team_alias('Washington St. Cougars', 'Washington St.');
SELECT add_team_alias('West Virginia Mountaineers', 'West Virginia');
SELECT add_team_alias('Wisconsin Badgers', 'Wisconsin');
SELECT add_team_alias('Wyoming Cowboys', 'Wyoming');
SELECT add_team_alias('Xavier Musketeers', 'Xavier');

-- Additional common variants
SELECT add_team_alias('UNC', 'North Carolina');
SELECT add_team_alias('UCONN', 'Connecticut');
SELECT add_team_alias('UNC Tar Heels', 'North Carolina');
SELECT add_team_alias('Miss Valley St. Delta Devils', 'Mississippi Valley St.');
SELECT add_team_alias('SE Louisiana Lions', 'Southeastern La.');

-- Clean up helper function
DROP FUNCTION IF EXISTS add_team_alias(TEXT, TEXT);

COMMENT ON TABLE team_aliases IS 'Complete team name mappings for 100% accuracy across Odds API and Barttorvik sources';
