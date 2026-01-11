-- Auto-generated migration: new teams + aliases (daily delta)
-- Source: teams/team_aliases created_at = CURRENT_DATE
BEGIN;

-- New teams
INSERT INTO teams (canonical_name, division)
VALUES
    ('Adams State', 'Non-D1'),
    ('Alice Loyd', 'Non-D1'),
    ('Anderson (Ind.)', 'Non-D1'),
    ('Anderson (S.C.)', 'Non-D1'),
    ('Andrews Univ.', 'Non-D1'),
    ('Angelo State', 'Non-D1'),
    ('Aquinas', 'Non-D1'),
    ('Arcadia', 'Non-D1'),
    ('Arkansas Baptist', 'Non-D1'),
    ('Arkansas-Fort Smith', 'Non-D1'),
    ('Arlington Baptist', 'Non-D1'),
    ('Asbury', 'Non-D1'),
    ('Aub.-Montgomery', 'Non-D1'),
    ('Augusta Jaguars', 'Non-D1'),
    ('Aurora', 'Non-D1'),
    ('Ave Maria', 'Non-D1'),
    ('Averett', 'Non-D1'),
    ('Avila', 'Non-D1'),
    ('Baldwin-Wallace', 'Non-D1'),
    ('Bard College', 'Non-D1'),
    ('Beacamo', 'Non-D1'),
    ('Belhaven', 'Non-D1'),
    ('Bellevue', 'Non-D1'),
    ('Benedictine', 'Non-D1'),
    ('Benedictine (AZ)', 'Non-D1'),
    ('Berea', 'Non-D1'),
    ('Berry', 'Non-D1'),
    ('Bethany', 'Non-D1'),
    ('Bethel (IN)', 'Non-D1'),
    ('Bethel (TN)', 'Non-D1'),
    ('Bethesda', 'Non-D1'),
    ('Bethune-Cookman', 'Non-D1'),
    ('Birmingham Southern', 'Non-D1'),
    ('Blackburn', 'Non-D1'),
    ('Bloomsburg', 'Non-D1'),
    ('Blue Mountain', 'Non-D1'),
    ('Bluefield State', 'Non-D1'),
    ('Bluffton', 'Non-D1'),
    ('Bob Jones', 'Non-D1'),
    ('Bowdoin', 'Non-D1'),
    ('Bowie', 'Non-D1'),
    ('Boyce', 'Non-D1'),
    ('Brescia', 'Non-D1'),
    ('Brevard College', 'Non-D1'),
    ('Brewton Parker', 'Non-D1'),
    ('Bridgewater College (VA)', 'Non-D1'),
    ('Bronxville', 'Non-D1'),
    ('Bryan', 'Non-D1'),
    ('Bryn Athyn', 'Non-D1'),
    ('Buffalo State', 'Non-D1'),
    ('CBS Ambassadors', 'Non-D1'),
    ('CS Fullerton', 'Non-D1'),
    ('CS Northridge', 'Non-D1'),
    ('CSU D. H.', 'Non-D1'),
    ('CU Irvine', 'Non-D1'),
    ('Cairn University', 'Non-D1'),
    ('Cal Maritime', 'Non-D1'),
    ('California Merced', 'Non-D1'),
    ('California State-Stanislaus Warriors', 'Non-D1'),
    ('Calumet College', 'Non-D1'),
    ('Calvary', 'Non-D1'),
    ('Campbellsville', 'Non-D1'),
    ('Campbellsville-Harrodsburg', 'Non-D1'),
    ('Capital Crusaders', 'Non-D1'),
    ('Carolina Christian', 'Non-D1'),
    ('Carolina University', 'Non-D1'),
    ('Carroll College', 'Non-D1'),
    ('Central Connecticut State', 'Non-D1'),
    ('Central Penn', 'Non-D1'),
    ('Central State (OH)', 'Non-D1'),
    ('Chadron S.', 'Non-D1'),
    ('Chadron St.', 'Non-D1'),
    ('Chaminade Silverswords', 'Non-D1'),
    ('Champion Christian Tigers', 'Non-D1'),
    ('Chapman Panthers', 'Non-D1'),
    ('Chatham', 'Non-D1'),
    ('Chestnut Hill', 'Non-D1'),
    ('Cheyney Wolves', 'Non-D1'),
    ('Christendom', 'Non-D1'),
    ('Citadel', 'Non-D1'),
    ('Clarke', 'Non-D1'),
    ('Clarks Summit', 'Non-D1'),
    ('Cleary University', 'Non-D1'),
    ('Coast Guard', 'Non-D1'),
    ('Coastal Georgia', 'Non-D1'),
    ('Coe', 'Non-D1'),
    ('Coker', 'Non-D1'),
    ('Colby-Sawyer', 'Non-D1'),
    ('Colorado Christian', 'Non-D1'),
    ('Colorado College', 'Non-D1'),
    ('Colorado Springs', 'Non-D1'),
    ('Colorado State - Pueblo', 'Non-D1'),
    ('Columbia International', 'Non-D1'),
    ('Concordia (MI)', 'Non-D1'),
    ('Concordia Cobbers', 'Non-D1'),
    ('Concordia St Paul', 'Non-D1'),
    ('Corban', 'Non-D1'),
    ('Covenant', 'Non-D1'),
    ('Crowley''s Ridge', 'Non-D1'),
    ('Crown College', 'Non-D1'),
    ('Curry', 'Non-D1'),
    ('D''Youville University', 'Non-D1'),
    ('Dakota Wesleyan', 'Non-D1'),
    ('Dallas Christian', 'Non-D1'),
    ('Dallas Univ.', 'Non-D1'),
    ('Dalton', 'Non-D1'),
    ('Davenport Univ.', 'Non-D1'),
    ('Davis & Elkins', 'Non-D1'),
    ('DePauw', 'Non-D1'),
    ('Dean', 'Non-D1'),
    ('Defiance College', 'Non-D1'),
    ('Delaware Valley Aggies', 'Non-D1'),
    ('Delta State', 'Non-D1'),
    ('Dickinson Red Devils', 'Non-D1'),
    ('Dickinson State', 'Non-D1'),
    ('Dillard', 'Non-D1'),
    ('Dist. of Columbia', 'Non-D1'),
    ('Doane Tigers', 'Non-D1'),
    ('Dubuque', 'Non-D1'),
    ('EWU Phantoms', 'Non-D1'),
    ('Earlham', 'Non-D1'),
    ('East-West University', 'Non-D1'),
    ('East. Washington', 'Non-D1'),
    ('Eastern Mennonite', 'Non-D1'),
    ('Eastern N.', 'Non-D1'),
    ('Eastern Oregon', 'Non-D1'),
    ('Ecclesia', 'Non-D1'),
    ('Edward Waters', 'Non-D1'),
    ('Elizabeth City', 'Non-D1'),
    ('Elms College', 'Non-D1'),
    ('Embry-Riddle (AZ)', 'Non-D1'),
    ('Emerson', 'Non-D1'),
    ('Endicott Gulls', 'Non-D1'),
    ('Erskine', 'Non-D1'),
    ('Eureka', 'Non-D1'),
    ('Evergreen State', 'Non-D1'),
    ('FDU-Florham', 'Non-D1'),
    ('Felician Golden', 'Non-D1'),
    ('Ferrum', 'Non-D1'),
    ('Fisher', 'Non-D1'),
    ('Fisk', 'Non-D1'),
    ('Florida National', 'Non-D1'),
    ('Florida Tech', 'Non-D1'),
    ('Fort Lauderdale', 'Non-D1'),
    ('Fort Valley State Wildcats', 'Non-D1'),
    ('Framingham State', 'Non-D1'),
    ('Franciscan University', 'Non-D1'),
    ('Franklin', 'Non-D1'),
    ('Franklin Pierce', 'Non-D1'),
    ('Fredonia State', 'Non-D1'),
    ('Fresno Pacific', 'Non-D1'),
    ('Friends University', 'Non-D1'),
    ('Frostburg', 'Non-D1'),
    ('Gallaudet Univ.', 'Non-D1'),
    ('George Fox', 'Non-D1'),
    ('Georgian Court Univ.', 'Non-D1'),
    ('Gilbert Buccaneers', 'Non-D1'),
    ('Goshen', 'Non-D1'),
    ('Greensboro', 'Non-D1'),
    ('Gwynedd-Mercy', 'Non-D1'),
    ('Hannibal-LaGrange', 'Non-D1'),
    ('Hardin Simmons', 'Non-D1'),
    ('Harris-Stowe', 'Non-D1'),
    ('Hartford', 'Non-D1'),
    ('Haskell', 'Non-D1'),
    ('Hawaii Pacific', 'Non-D1'),
    ('Hawaii at Hilo', 'Non-D1'),
    ('Heidelberg', 'Non-D1'),
    ('Hendrix College', 'Non-D1'),
    ('Holy', 'Non-D1'),
    ('Holy Cross Saints', 'Non-D1'),
    ('Hood', 'Non-D1'),
    ('Houghton', 'Non-D1'),
    ('Howard Payne', 'Non-D1'),
    ('IUPUC', 'Non-D1'),
    ('Illinois (Chi.)', 'Non-D1'),
    ('Illinois Tech', 'Non-D1'),
    ('Immaculata', 'Non-D1'),
    ('Indiana-Northwest', 'Non-D1'),
    ('Jamestown Jimmies', 'Non-D1'),
    ('Jarvis Christian', 'Non-D1'),
    ('John Brown', 'Non-D1'),
    ('John Jay', 'Non-D1'),
    ('John Melvin', 'Non-D1'),
    ('Johnson & Wales (RI)', 'Non-D1'),
    ('Johnson Royals', 'Non-D1'),
    ('Johnson Suns', 'Non-D1'),
    ('Johnson and Wales (NC)', 'Non-D1'),
    ('Judson', 'Non-D1'),
    ('Justice College', 'Non-D1'),
    ('Kansas Christian', 'Non-D1'),
    ('Kean', 'Non-D1'),
    ('Keiser', 'Non-D1'),
    ('Kentucky Christian', 'Non-D1'),
    ('Kentucky State', 'Non-D1'),
    ('Kentucky Wesleyan Panthers', 'Non-D1'),
    ('Keystone', 'Non-D1'),
    ('King Tornado', 'Non-D1'),
    ('LSU-Alexandria', 'Non-D1'),
    ('LSU-Shreveport', 'Non-D1'),
    ('La Grange', 'Non-D1'),
    ('La Sierra', 'Non-D1'),
    ('La Verne', 'Non-D1'),
    ('Lake Erie', 'Non-D1'),
    ('Lake Superior', 'Non-D1'),
    ('Lakeland', 'Non-D1'),
    ('Lancaster', 'Non-D1'),
    ('Lane College', 'Non-D1'),
    ('Le Tourneau', 'Non-D1'),
    ('Lehman College', 'Non-D1'),
    ('Lemoyne-Owen', 'Non-D1'),
    ('Lesley', 'Non-D1'),
    ('Lewis & Clark', 'Non-D1'),
    ('Lewis &. Clark State', 'Non-D1'),
    ('Life Pacific', 'Non-D1'),
    ('Life University', 'Non-D1'),
    ('Limestone College', 'Non-D1'),
    ('Lincoln Mo.', 'Non-D1'),
    ('Lincoln University (CA)', 'Non-D1'),
    ('Linfield', 'Non-D1'),
    ('Livingstone', 'Non-D1'),
    ('Loras Duhawks', 'Non-D1'),
    ('Louisiana Christian', 'Non-D1'),
    ('Louisiana Lafayette', 'Non-D1'),
    ('Lourdes', 'Non-D1'),
    ('Loyola NO', 'Non-D1'),
    ('Luther Norse', 'Non-D1'),
    ('Lynchburg', 'Non-D1'),
    ('Lyndon State Hornets', 'Non-D1'),
    ('Lynn University', 'Non-D1'),
    ('Lyon', 'Non-D1'),
    ('MN-Crookston', 'Non-D1'),
    ('MUW Owls', 'Non-D1'),
    ('Maine-Augusta', 'Non-D1'),
    ('Maine-Fort Kent', 'Non-D1'),
    ('Maine-Presque', 'Non-D1'),
    ('Malone Pioneers', 'Non-D1'),
    ('Manhattanville', 'Non-D1'),
    ('Manor College', 'Non-D1'),
    ('Mansfield', 'Non-D1'),
    ('Marian Sabres', 'Non-D1'),
    ('Mary Baldwin', 'Non-D1'),
    ('Maryville', 'Non-D1'),
    ('Marywood Pacers', 'Non-D1'),
    ('Massachusetts-Boston', 'Non-D1'),
    ('Mayaguez Bulldogs', 'Non-D1'),
    ('Mayville St', 'Non-D1'),
    ('McMurry', 'Non-D1'),
    ('McPherson', 'Non-D1'),
    ('Md.-East. Shore', 'Non-D1'),
    ('Medgar Evers', 'Non-D1'),
    ('Menlo', 'Non-D1'),
    ('Mercy', 'Non-D1'),
    ('Miami-Hamilton', 'Non-D1'),
    ('Michigan Tech', 'Non-D1'),
    ('Mid-America Christian', 'Non-D1'),
    ('Mid-Atlantic', 'Non-D1'),
    ('Middle Georgia State', 'Non-D1'),
    ('Middle Tenn. St.', 'Non-D1'),
    ('Midway', 'Non-D1'),
    ('Milligan', 'Non-D1'),
    ('Millsaps', 'Non-D1'),
    ('Milwaukee School of Engineering', 'Non-D1'),
    ('Misericordia', 'Non-D1'),
    ('Miss. Valley St.', 'Non-D1'),
    ('Mississippi Coll.', 'Non-D1'),
    ('Missouri Baptist', 'Non-D1'),
    ('Missouri Southern State', 'Non-D1'),
    ('Mitchell', 'Non-D1'),
    ('Mobile', 'Non-D1'),
    ('Molloy', 'Non-D1'),
    ('Monmouth (IL)', 'Non-D1'),
    ('Montana State-Northern', 'Non-D1'),
    ('Montana Tech', 'Non-D1'),
    ('Montevallo', 'Non-D1'),
    ('Montreat College', 'Non-D1'),
    ('Morehouse', 'Non-D1'),
    ('Morris College', 'Non-D1'),
    ('Morrisville State', 'Non-D1'),
    ('Mount Aloysius', 'Non-D1'),
    ('Mount Marty', 'Non-D1'),
    ('Mount Olive Trojans', 'Non-D1'),
    ('Mount St. Mary College', 'Non-D1'),
    ('Mount St. Vincent', 'Non-D1'),
    ('Muskingum', 'Non-D1'),
    ('N. Carolina A&T', 'Non-D1'),
    ('N. Carolina Central', 'Non-D1'),
    ('N. New Mexico', 'Non-D1'),
    ('N.C. Wesleyan', 'Non-D1'),
    ('Navajo Skyhawks', 'Non-D1'),
    ('Nazareth', 'Non-D1'),
    ('Nebraska O.', 'Non-D1'),
    ('Nelson', 'Non-D1'),
    ('Neumann', 'Non-D1'),
    ('New College (FL)', 'Non-D1'),
    ('Newberry', 'Non-D1'),
    ('Newport Apprentice', 'Non-D1'),
    ('Nobel Knights', 'Non-D1'),
    ('North American Stallions', 'Non-D1'),
    ('North Central Cardinals', 'Non-D1'),
    ('North Central Rams', 'Non-D1'),
    ('North Greenville', 'Non-D1'),
    ('North Park', 'Non-D1'),
    ('North Texas-Dallas', 'Non-D1'),
    ('Northeastern State', 'Non-D1'),
    ('Northern Vermont - Johnson', 'Non-D1'),
    ('Northland', 'Non-D1'),
    ('Northwest', 'Non-D1'),
    ('Northwest Indian', 'Non-D1'),
    ('Northwest Nazarene', 'Non-D1'),
    ('Northwood', 'Non-D1'),
    ('Notre Dame MD', 'Non-D1'),
    ('Oak Hills Christian', 'Non-D1'),
    ('Oakland City', 'Non-D1'),
    ('Oakwood', 'Non-D1'),
    ('Occidental', 'Non-D1'),
    ('Oglethorpe', 'Non-D1'),
    ('Ohio Christian', 'Non-D1'),
    ('Ohio Dominican', 'Non-D1'),
    ('Ohio Wesleyan', 'Non-D1'),
    ('Old Westbury', 'Non-D1'),
    ('Oneonta State', 'Non-D1'),
    ('Ouachita Baptist', 'Non-D1'),
    ('Our Lady Of The Lake', 'Non-D1'),
    ('Ozark Christian', 'Non-D1'),
    ('Pacific Boxers', 'Non-D1'),
    ('Pacific Lutheran', 'Non-D1'),
    ('Pacific Union', 'Non-D1'),
    ('Paul Quinn', 'Non-D1'),
    ('Penn St Altoona', 'Non-D1'),
    ('Penn St.-Allegheny', 'Non-D1'),
    ('Penn State Brandywine', 'Non-D1'),
    ('Penn State Wilkes-Barre', 'Non-D1'),
    ('Penn State-Fayette', 'Non-D1'),
    ('Penn State-New Kensington', 'Non-D1'),
    ('Penn State-Schuylkill', 'Non-D1'),
    ('Penn State-Scranton', 'Non-D1'),
    ('Penn State-Shenango', 'Non-D1'),
    ('Penn State-York', 'Non-D1'),
    ('Pfeiffer Falcons', 'Non-D1'),
    ('Piedmont', 'Non-D1'),
    ('Pittsburgh - Greensburg', 'Non-D1'),
    ('Pittsburgh Bradford', 'Non-D1'),
    ('Plattsburgh', 'Non-D1'),
    ('Point Chargers', 'Non-D1'),
    ('Point Loma', 'Non-D1'),
    ('Point Park Pioneers', 'Non-D1'),
    ('Polytechnic', 'Non-D1'),
    ('Portland Bible', 'Non-D1'),
    ('Pratt Cannoneers', 'Non-D1'),
    ('Purdue Northwest', 'Non-D1'),
    ('Queens College', 'Non-D1'),
    ('Queens Royals', 'Non-D1'),
    ('Randall University', 'Non-D1'),
    ('Randolph', 'Non-D1'),
    ('Randolph-Macon', 'Non-D1'),
    ('Regent University', 'Non-D1'),
    ('Regis College', 'Non-D1'),
    ('Reinhardt', 'Non-D1'),
    ('Rhode Island Anchormen', 'Non-D1'),
    ('Rhodes Lynx', 'Non-D1'),
    ('Rivier', 'Non-D1'),
    ('Roberts Wesleyan', 'Non-D1'),
    ('Rockford University', 'Non-D1'),
    ('Rocky Mountain', 'Non-D1'),
    ('Rogers State Hillcats', 'Non-D1'),
    ('Rosemont', 'Non-D1'),
    ('Rust College', 'Non-D1'),
    ('S''western (Texas)', 'Non-D1'),
    ('SAGU', 'Non-D1'),
    ('SE Louisiana', 'Non-D1'),
    ('SMWC Pomeroys', 'Non-D1'),
    ('SUNY Potsdam', 'Non-D1'),
    ('SUNY-Brockport', 'Non-D1'),
    ('SUNY-Canton', 'Non-D1'),
    ('SUNY-Delhi', 'Non-D1'),
    ('SUNY-Purchase', 'Non-D1'),
    ('Saginaw Valley', 'Non-D1'),
    ('Saint Katherine', 'Non-D1'),
    ('Saint Mary', 'Non-D1'),
    ('San Francisco State', 'Non-D1'),
    ('Sarah Lawrence', 'Non-D1'),
    ('Schreiner', 'Non-D1'),
    ('Shawnee State', 'Non-D1'),
    ('Siena Heights', 'Non-D1'),
    ('Sonoma State', 'Non-D1'),
    ('South Dakota Mines', 'Non-D1'),
    ('Southern Oregon', 'Non-D1'),
    ('Southern Univ.', 'Non-D1'),
    ('Southern Virginia', 'Non-D1'),
    ('Southern W.', 'Non-D1'),
    ('Southern-New O.', 'Non-D1'),
    ('Southwest Adventist', 'Non-D1'),
    ('Southwest Minnesota State', 'Non-D1'),
    ('Southwest Mustangs', 'Non-D1'),
    ('Southwestern Adventist', 'Non-D1'),
    ('Southwestern Christian', 'Non-D1'),
    ('Southwestern Oklahoma', 'Non-D1'),
    ('Spalding', 'Non-D1'),
    ('Spartanburg', 'Non-D1'),
    ('Spring Hill', 'Non-D1'),
    ('Springfield Pride', 'Non-D1'),
    ('St. Ambrose', 'Non-D1'),
    ('St. Andrews', 'Non-D1'),
    ('St. Augustine', 'Non-D1'),
    ('St. Elizabeth', 'Non-D1'),
    ('St. Francis (ILL)', 'Non-D1'),
    ('St. Francis (PA)', 'Non-D1'),
    ('St. Francis BKN Terriers', 'Non-D1'),
    ('St. John''s (N.Y.)', 'Non-D1'),
    ('St. Joseph''s (Brooklyn)', 'Non-D1'),
    ('St. Joseph''s (NY-LI)', 'Non-D1'),
    ('St. Louis Billikens', 'Non-D1'),
    ('St. Louis College of Pharmacy', 'Non-D1'),
    ('St. Mary''s (MD)', 'Non-D1'),
    ('St. Mary''s (MN)', 'Non-D1'),
    ('St. Marys (CA)', 'Non-D1'),
    ('St. Norbert', 'Non-D1'),
    ('St. Peters', 'Non-D1'),
    ('St. Thomas (Minn.)', 'Non-D1'),
    ('St. Thomas (TX)', 'Non-D1'),
    ('St. Vincent', 'Non-D1'),
    ('St. Xavier', 'Non-D1'),
    ('Stanton', 'Non-D1'),
    ('Sterling College', 'Non-D1'),
    ('Steubenville', 'Non-D1'),
    ('Sul Ross State', 'Non-D1'),
    ('Suny Maritime', 'Non-D1'),
    ('Suny Oneonta', 'Non-D1'),
    ('TX A&M Commerce', 'Non-D1'),
    ('Tabor', 'Non-D1'),
    ('Talladega', 'Non-D1'),
    ('Tarleton', 'Non-D1'),
    ('Taylor', 'Non-D1'),
    ('Texas A&M SA Jaguars', 'Non-D1'),
    ('Texas A&M-CC', 'Non-D1'),
    ('Texas A&M-Kingsville', 'Non-D1'),
    ('Texas College', 'Non-D1'),
    ('Texas Dallas', 'Non-D1'),
    ('Texas Lutheran', 'Non-D1'),
    ('Texas Texarkana Eagles', 'Non-D1'),
    ('Texas Wesleyan', 'Non-D1'),
    ('Texas-Permian Basin', 'Non-D1'),
    ('Texas-Tyler Patriots', 'Non-D1'),
    ('Thomas (ME)', 'Non-D1'),
    ('Thomas College', 'Non-D1'),
    ('Thomas Univ.', 'Non-D1'),
    ('Tiffin', 'Non-D1'),
    ('Toccoa Falls', 'Non-D1'),
    ('Trevecca Nazarene', 'Non-D1'),
    ('Trinity (FL)', 'Non-D1'),
    ('Trinity (IL)', 'Non-D1'),
    ('Trinity Baptist', 'Non-D1'),
    ('Trinity of Texas', 'Non-D1'),
    ('Truett-McConnell', 'Non-D1'),
    ('Truman State', 'Non-D1'),
    ('Tusculum', 'Non-D1'),
    ('UALR', 'Non-D1'),
    ('USMMA', 'Non-D1'),
    ('UW-Stout', 'Non-D1'),
    ('Union Bulldogs', 'Non-D1'),
    ('University of Sciences', 'Non-D1'),
    ('University of the Cumberlands (KY)', 'Non-D1'),
    ('Utah Valley State', 'Non-D1'),
    ('VA Wesleyan', 'Non-D1'),
    ('Valley City State Vikings', 'Non-D1'),
    ('Valley Forge', 'Non-D1'),
    ('Vanguard Lions', 'Non-D1'),
    ('Vassar', 'Non-D1'),
    ('Vermont State - Johnson', 'Non-D1'),
    ('Vermont State - RK', 'Non-D1'),
    ('Virginia-Lynchburg', 'Non-D1'),
    ('Virginia-Wise', 'Non-D1'),
    ('Voorhees', 'Non-D1'),
    ('Waldorf College', 'Non-D1'),
    ('Walla Walla', 'Non-D1'),
    ('Warner Pacific', 'Non-D1'),
    ('Warner University', 'Non-D1'),
    ('Warren Wilson', 'Non-D1'),
    ('Washington & Lee', 'Non-D1'),
    ('Washington Adventist', 'Non-D1'),
    ('Washington Coll', 'Non-D1'),
    ('Wayland Baptist', 'Non-D1'),
    ('Webber Int''l', 'Non-D1'),
    ('Wells College', 'Non-D1'),
    ('Wesleyan Univ.', 'Non-D1'),
    ('West Virginia Wesleyan', 'Non-D1'),
    ('Westcliff', 'Non-D1'),
    ('Western Colorado', 'Non-D1'),
    ('Western N. M.', 'Non-D1'),
    ('Western Oregon', 'Non-D1'),
    ('Westfield State', 'Non-D1'),
    ('Westminster Blue Jays', 'Non-D1'),
    ('Westminster Titans', 'Non-D1'),
    ('Westminster UT', 'Non-D1'),
    ('Westmont Warriors', 'Non-D1'),
    ('Whittier', 'Non-D1'),
    ('Wilberforce', 'Non-D1'),
    ('Wiley', 'Non-D1'),
    ('Wilkes Colonels', 'Non-D1'),
    ('Willamette', 'Non-D1'),
    ('William Carey', 'Non-D1'),
    ('William Jessup', 'Non-D1'),
    ('William Peace', 'Non-D1'),
    ('William Woods', 'Non-D1'),
    ('Wilson College', 'Non-D1'),
    ('Wisc. Green Bay', 'Non-D1'),
    ('Wisc. Milwaukee', 'Non-D1'),
    ('Wisconsin-Stout', 'Non-D1'),
    ('Wittenberg Tigers', 'Non-D1'),
    ('Worcester State', 'Non-D1'),
    ('Worcester Tech', 'Non-D1'),
    ('Xavier (LA)', 'Non-D1'),
    ('York', 'Non-D1'),
    ('York College', 'Non-D1')
ON CONFLICT (canonical_name) DO NOTHING;

-- New aliases
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Adams State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Adams State'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Alabama State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Alabama St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Alabama State Hornets', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Alabama St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Alcorn State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Alcorn St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Alcorn State Braves', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Alcorn St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Alice Loyd', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Alice Loyd'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'American University', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'American'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'American University Eagles', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'American'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Anderson (Ind.)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Anderson (Ind.)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Anderson (S.C.)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Anderson (S.C.)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Andrews Univ.', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Andrews Univ.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Angelo State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Angelo State'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Aquinas', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Aquinas'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Arcadia', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Arcadia'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Arkansas Baptist', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Arkansas Baptist'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Arkansas-Fort Smith', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Arkansas-Fort Smith'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Arkansas-Pine Bluff', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Arkansas-Pine Bluff Golden Lions'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Arlington Baptist Patriots', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Arlington Baptist'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Army Black Knights', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Army'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Asbury', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Asbury'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Aub.-Montgomery', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Aub.-Montgomery'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Augusta Jaguars', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Augusta Jaguars'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Aurora', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Aurora'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Ave Maria', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Ave Maria'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Averett', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Averett'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Avila', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Avila'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Baldwin-Wallace', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Baldwin-Wallace'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Bard College', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Bard College'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Beacamo', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Beacamo'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Belhaven', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Belhaven'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Bellevue', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Bellevue'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Benedictine', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Benedictine'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Benedictine (AZ)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Benedictine (AZ)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Berea', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Berea'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Berry', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Berry'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Bethany', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Bethany'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Bethel (IN)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Bethel (IN)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Bethel (TN)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Bethel (TN)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Bethesda', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Bethesda'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Bethune-Cookman', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Bethune-Cookman'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Birmingham Southern', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Birmingham Southern'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Blackburn', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Blackburn'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Bloomsburg', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Bloomsburg'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Blue Mountain', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Blue Mountain'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Bluefield State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Bluefield State'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Bluffton', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Bluffton'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Bob Jones', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Bob Jones'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Bowdoin', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Bowdoin'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Bowie', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Bowie'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Boyce', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Boyce'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Brescia', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Brescia'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Brevard College', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Brevard College'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Brewton Parker', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Brewton Parker'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Bridgewater College (VA)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Bridgewater College (VA)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Bronxville', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Bronxville'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Bryan', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Bryan'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Bryant University', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Bryant'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Bryn Athyn', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Bryn Athyn'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Buffalo State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Buffalo State'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'CBS Ambassadors', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'CBS Ambassadors'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'CS Fullerton', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'CS Fullerton'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'CS Northridge', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'CS Northridge'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'CSU Bakersfield', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'CSU Bakersfield Roadrunners'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'CSU D. H.', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'CSU D. H.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'CU Irvine', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'CU Irvine'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Cairn', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Cairn University'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Cairn University Highlanders', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Cairn University'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Cal Maritime Keelhaulers', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Cal Maritime'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'California Golden Bears', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'California'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'California Merced', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'California Merced'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'California State-Stanislaus Warriors', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'California State-Stanislaus Warriors'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Calumet College', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Calumet College'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Calvary', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Calvary'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Campbell Fighting Camels', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Campbell'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Campbellsville', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Campbellsville'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Campbellsville-Harrodsburg', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Campbellsville-Harrodsburg'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Capital Crusaders', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Capital Crusaders'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Carolina Christian', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Carolina Christian'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Carolina University', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Carolina University'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Carroll College', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Carroll College'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Central Connecticut State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Central Connecticut State'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Central Penn', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Central Penn'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Central State (OH)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Central State (OH)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Chadron S.', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Chadron S.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Chadron State Eagles', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Chadron St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Chaminade Silverswords', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Chaminade Silverswords'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Champion Christian Tigers', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Champion Christian Tigers'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Chapman Panthers', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Chapman Panthers'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Chatham', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Chatham'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Chattanooga Mocs', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Chattanooga'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Chestnut Hill', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Chestnut Hill'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Cheyney Wolves', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Cheyney Wolves'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Chicago State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Chicago St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Chicago State Cougars', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Chicago St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Christendom', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Christendom'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Citadel', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Citadel'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Clarke', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Clarke'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Clarks Summit', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Clarks Summit'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Cleary University', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Cleary University'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Coast Guard', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Coast Guard'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Coastal Georgia', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Coastal Georgia'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Coe', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Coe'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Coker', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Coker'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Colby-Sawyer', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Colby-Sawyer'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Colgate Raiders', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Colgate'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Colorado Christian', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Colorado Christian'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Colorado Christian Cougars', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Colorado'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Colorado College', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Colorado College'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Colorado Springs', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Colorado Springs'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Colorado State - Pueblo', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Colorado State - Pueblo'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Columbia International', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Columbia International'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Columbia International Rams', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Columbia'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Concordia (MI)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Concordia (MI)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Concordia Cobbers', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Concordia Cobbers'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Concordia St Paul', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Concordia St Paul'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Coppin State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Coppin St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Coppin State Eagles', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Coppin St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Corban', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Corban'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Covenant', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Covenant'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Crowley''s Ridge', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Crowley''s Ridge'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Crown College', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Crown College'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Curry', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Curry'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'D''Youville University', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'D''Youville University'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Dakota Wesleyan Tigers', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Dakota Wesleyan'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Dallas Christian', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Dallas Christian'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Dallas Univ.', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Dallas Univ.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Dalton', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Dalton'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Davenport Univ.', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Davenport Univ.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Davis & Elkins', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Davis & Elkins'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'DePauw', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'DePauw'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Dean', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Dean'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Defiance College', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Defiance College'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Delaware State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Delaware St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Delaware State Hornets', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Delaware St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Delaware Valley Aggies', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Delaware Valley Aggies'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Delta State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Delta State'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Dickinson Red Devils', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Dickinson Red Devils'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Dickinson State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Dickinson State'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Dillard', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Dillard'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Dist. of Columbia', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Dist. of Columbia'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Doane Tigers', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Doane Tigers'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Drexel Dragons', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Drexel'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Dubuque', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Dubuque'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'EWU Phantoms', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'EWU Phantoms'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Earlham', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Earlham'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'East-West University Phantoms', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'East-West University'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'East. Washington', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'East. Washington'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Eastern Mennonite', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Eastern Mennonite'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Eastern N.', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Eastern N.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Eastern Oregon', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Eastern Oregon'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Ecclesia Royals', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Ecclesia'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Edward Waters', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Edward Waters'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Elizabeth City', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Elizabeth City'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Elms College', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Elms College'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Embry-Riddle (AZ)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Embry-Riddle (AZ)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Emerson', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Emerson'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Endicott Gulls', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Endicott Gulls'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Erskine', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Erskine'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Eureka', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Eureka'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Evergreen State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Evergreen State'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'FDU-Florham', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'FDU-Florham'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Felician Golden', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Felician Golden'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Ferrum', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Ferrum'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Fisher', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Fisher'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Fisk', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Fisk'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Florida National', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Florida National'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Florida National Conquistadors', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Florida'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Florida Tech', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Florida Tech'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Fort Lauderdale', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Fort Lauderdale'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Fort Valley State Wildcats', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Fort Valley State Wildcats'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Framingham State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Framingham State'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Franciscan University Barons', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Franciscan University'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Franklin', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Franklin'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Franklin Pierce', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Franklin Pierce'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Fredonia State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Fredonia State'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Fresno Pacific', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Fresno Pacific'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Friends University', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Friends University'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Frostburg', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Frostburg'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Gallaudet Univ.', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Gallaudet Univ.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Gardner-Webb Runnin'' Bulldogs', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Gardner Webb'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'George Fox', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'George Fox'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'George Washington Revolutionaries', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'George Washington'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Georgian Court Univ.', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Georgian Court Univ.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Gilbert Buccaneers', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Gilbert Buccaneers'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Goshen', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Goshen'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Grambling Tigers', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Grambling St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Grand Canyon Lopes', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Grand Canyon'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Greensboro', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Greensboro'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Gwynedd-Mercy', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Gwynedd-Mercy'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Hannibal-LaGrange', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Hannibal-LaGrange'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Hardin Simmons', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Hardin Simmons'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Harris-Stowe', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Harris-Stowe'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Hartford', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Hartford'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Haskell', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Haskell'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Hawaii Pacific', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Hawaii Pacific'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Hawaii at Hilo', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Hawaii at Hilo'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Heidelberg', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Heidelberg'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Hendrix College', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Hendrix College'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Holy', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Holy'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Holy Cross Saints', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Holy Cross Saints'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Hood', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Hood'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Houghton', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Houghton'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Howard Payne', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Howard Payne'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'IU Indianapolis Jaguars', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Indiana'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'IUPUC', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'IUPUC'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Idaho State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Idaho St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Illinois (Chi.)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Illinois (Chi.)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Illinois Tech', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Illinois Tech'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Immaculata', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Immaculata'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Indiana-Northwest', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Indiana-Northwest'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Jackson State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Jackson St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Jackson State Tigers', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Jackson St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Jacksonville State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Jacksonville St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Jacksonville State Gamecocks', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Jacksonville St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Jamestown Jimmies', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Jamestown Jimmies'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Jarvis Christian', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Jarvis Christian'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'John Brown', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'John Brown'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'John Jay', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'John Jay'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'John Melvin', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'John Melvin'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Johnson & Wales (RI)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Johnson & Wales (RI)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Johnson Royals', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Johnson Royals'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Johnson Suns', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Johnson Suns'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Johnson and Wales (NC)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Johnson and Wales (NC)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Judson', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Judson'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Justice College', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Justice College'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Kansas Christian', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Kansas Christian'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Kansas City Roos', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Kansas'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Kean', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Kean'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Keiser', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Keiser'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Kennesaw State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Kennesaw St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Kennesaw State Owls', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Kennesaw St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Kentucky Christian', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Kentucky Christian'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Kentucky State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Kentucky State'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Kentucky Wesleyan Panthers', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Kentucky Wesleyan Panthers'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Keystone', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Keystone'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'King Tornado', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'King Tornado'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'LSU-Alexandria', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'LSU-Alexandria'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'LSU-Shreveport', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'LSU-Shreveport'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'La Grange', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'La Grange'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'La Sierra Golden Eagles', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'La Sierra'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'La Verne', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'La Verne'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Lake Erie', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Lake Erie'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Lake Superior', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Lake Superior'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Lakeland', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Lakeland'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Lancaster', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Lancaster'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Lane College', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Lane College'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Le Tourneau', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Le Tourneau'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Lehman College', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Lehman College'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Lemoyne-Owen', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Lemoyne-Owen'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Lesley', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Lesley'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Lewis & Clark', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Lewis & Clark'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Lewis &. Clark State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Lewis &. Clark State'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Life Pacific', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Life Pacific'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Life University', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Life University'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Limestone College', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Limestone College'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Lincoln Mo.', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Lincoln Mo.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Lincoln University (CA) Oaklanders', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Lincoln University (CA)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Linfield', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Linfield'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Livingstone', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Livingstone'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Long Beach State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Long Beach St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Long Beach State Beach', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Long Beach St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Long Island University Sharks', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'LIU'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Loras Duhawks', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Loras Duhawks'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Louisiana Christian', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Louisiana Christian'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Louisiana Lafayette', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Louisiana Lafayette'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Lourdes', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Lourdes'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Loyola NO', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Loyola NO'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Luther Norse', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Luther Norse'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Lynchburg', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Lynchburg'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Lyndon State Hornets', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Lyndon State Hornets'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Lynn University', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Lynn University'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Lyon', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Lyon'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'MN-Crookston', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'MN-Crookston'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'MUW Owls', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'MUW Owls'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Maine Black Bears', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Maine'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Maine-Augusta', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Maine-Augusta'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Maine-Fort Kent', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Maine-Fort Kent'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Maine-Presque', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Maine-Presque'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Malone Pioneers', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Malone Pioneers'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Manhattanville', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Manhattanville'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Manor College', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Manor College'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Mansfield', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Mansfield'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Marian Sabres', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Marian Sabres'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Mary Baldwin', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Mary Baldwin'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Maryland Eastern Shore Hawks', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Maryland E. Shore'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Maryville', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Maryville'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Marywood Pacers', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Marywood Pacers'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Massachusetts-Boston', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Massachusetts-Boston'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Mayaguez Bulldogs', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Mayaguez Bulldogs'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Mayville St', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Mayville St'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'McMurry', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'McMurry'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'McPherson', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'McPherson'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Md.-East. Shore', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Md.-East. Shore'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Medgar Evers', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Medgar Evers'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Menlo', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Menlo'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Mercy', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Mercy'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Miami-Hamilton', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Miami-Hamilton'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Michigan Tech', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Michigan Tech'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Mid-America Christian', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Mid-America Christian'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Mid-Atlantic', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Mid-Atlantic'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Middle Georgia State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Middle Georgia State'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Middle Tenn. St.', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Middle Tenn. St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Midway', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Midway'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Milligan Buffaloes', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Milligan'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Millsaps', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Millsaps'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Milwaukee School of Engineering', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Milwaukee School of Engineering'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Misericordia', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Misericordia'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Miss. Valley St.', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Miss. Valley St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Mississippi Coll.', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Mississippi Coll.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Mississippi Valley State Delta Devils', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Mississippi Valley St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Missouri Baptist', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Missouri Baptist'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Missouri Southern State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Missouri Southern State'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Mitchell', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Mitchell'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Mobile', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Mobile'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Molloy', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Molloy'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Monmouth (IL)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Monmouth (IL)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Montana State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Montana St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Montana State Bobcats', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Montana St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Montana State-Northern', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Montana State-Northern'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Montana Tech', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Montana Tech'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Montevallo', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Montevallo'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Montreat College', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Montreat College'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Morehead State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Morehead St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Morehead State Eagles', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Morehead St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Morehouse Maroon Tigers', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Morehouse'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Morgan State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Morgan St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Morgan State Bears', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Morgan St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Morris College', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Morris College'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Morrisville State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Morrisville State'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Mount Aloysius', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Mount Aloysius'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Mount Marty', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Mount Marty'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Mount Olive Trojans', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Mount Olive Trojans'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Mount St. Mary College', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Mount St. Mary College'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Mount St. Vincent', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Mount St. Vincent'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Muskingum', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Muskingum'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'N. Carolina A&T', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'N. Carolina A&T'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'N. Carolina Central', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'N. Carolina Central'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'N.C. Wesleyan', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'N.C. Wesleyan'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Navajo Skyhawks', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Navajo Skyhawks'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Nazareth', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Nazareth'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Nebraska O.', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Nebraska O.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Nelson', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Nelson'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Neumann', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Neumann'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'New College (FL)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'New College (FL)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'New Mexico Cowboys', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'New Mexico'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'New Mexico State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'New Mexico St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'New Mexico State Aggies', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'New Mexico St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Newberry', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Newberry'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Newport Apprentice', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Newport Apprentice'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Nicholls Colonels', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Nicholls'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Nobel Knights', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Nobel Knights'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Norfolk State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Norfolk St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Norfolk State Spartans', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Norfolk St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'North American Stallions', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'North American Stallions'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'North Central Cardinals', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'North Central Cardinals'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'North Central Rams', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'North Central Rams'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'North Dakota State Bison', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'North Dakota St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'North Greenville Crusaders', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'North Greenville'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'North Park', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'North Park'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'North Texas-Dallas', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'North Texas-Dallas'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Northeastern State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Northeastern State'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Northern New Mexico', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'N. New Mexico'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Northern New Mexico Eagles', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'N. New Mexico'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Northern Vermont - Johnson', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Northern Vermont - Johnson'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Northland', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Northland'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Northwest', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Northwest'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Northwest Indian', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Northwest Indian'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Northwest Nazarene', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Northwest Nazarene'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Northwestern State Demons', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Northwestern St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Northwood', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Northwood'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Notre Dame MD', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Notre Dame MD'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Oak Hills Christian', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Oak Hills Christian'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Oakland City', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Oakland City'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Oakwood Ambassadors', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Oakwood'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Occidental', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Occidental'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Oglethorpe', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Oglethorpe'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Ohio Christian', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Ohio Christian'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Ohio Dominican', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Ohio Dominican'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Ohio Wesleyan', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Ohio Wesleyan'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Old Westbury', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Old Westbury'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Oneonta State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Oneonta State'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Oregon State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Oregon St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Oregon State Beavers', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Oregon St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Ouachita Baptist', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Ouachita Baptist'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Our Lady Of The Lake', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Our Lady Of The Lake'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Ozark Christian', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Ozark Christian'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Pacific Boxers', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Pacific Boxers'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Pacific Lutheran', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Pacific Lutheran'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Pacific Union', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Pacific Union'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Paul Quinn', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Paul Quinn'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Penn St Altoona', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Penn St Altoona'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Penn St.-Allegheny', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Penn St.-Allegheny'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Penn State Brandywine', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Penn State Brandywine'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Penn State Wilkes-Barre', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Penn State Wilkes-Barre'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Penn State-Fayette', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Penn State-Fayette'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Penn State-New Kensington', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Penn State-New Kensington'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Penn State-Schuylkill', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Penn State-Schuylkill'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Penn State-Scranton', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Penn State-Scranton'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Penn State-Shenango', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Penn State-Shenango'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Penn State-York', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Penn State-York'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Pfeiffer Falcons', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Pfeiffer Falcons'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Piedmont', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Piedmont'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Pittsburgh - Greensburg', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Pittsburgh - Greensburg'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Pittsburgh Bradford', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Pittsburgh Bradford'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Plattsburgh', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Plattsburgh'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Point Chargers', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Point Chargers'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Point Loma', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Point Loma'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Point Park Pioneers', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Point Park Pioneers'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Polytechnic', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Polytechnic'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Portland Bible', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Portland Bible'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Portland State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Portland St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Pratt Cannoneers', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Pratt Cannoneers'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Purdue Fort Wayne Mastodons', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Purdue Fort Wayne'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Purdue Northwest', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Purdue Northwest'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Queens College', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Queens College'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Queens Royals', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Queens Royals'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Randall University', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Randall University'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Randolph', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Randolph'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Randolph-Macon', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Randolph-Macon'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Regent University', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Regent University'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Regis College', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Regis College'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Reinhardt', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Reinhardt'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Rhode Island Anchormen', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Rhode Island Anchormen'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Rhodes Lynx', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Rhodes Lynx'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Rivier', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Rivier'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Roberts Wesleyan', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Roberts Wesleyan'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Rockford University', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Rockford University'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Rocky Mountain', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Rocky Mountain'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Rogers State Hillcats', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Rogers State Hillcats'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Rosemont', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Rosemont'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Rust College', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Rust College'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'S''western (Texas)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'S''western (Texas)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'SAGU', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'SAGU'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'SE Louisiana', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'SE Louisiana'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'SMWC Pomeroys', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'SMWC Pomeroys'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'SUNY Potsdam', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'SUNY Potsdam'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'SUNY-Brockport', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'SUNY-Brockport'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'SUNY-Canton Roos', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'SUNY-Canton'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'SUNY-Delhi', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'SUNY-Delhi'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'SUNY-Purchase', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'SUNY-Purchase'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Sacramento State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Sacramento St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Sacramento State Hornets', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Sacramento St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Saginaw Valley', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Saginaw Valley'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Saint Katherine', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Saint Katherine'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Saint Mary', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Saint Mary'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Sam Houston Bearkats', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Sam Houston St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'San Francisco State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'San Francisco State'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'San José State Spartans', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'San Jose St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Sarah Lawrence Gryphons', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Sarah Lawrence'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Schreiner Mountaineers', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Schreiner'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Seattle U Redhawks', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Seattle'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Shawnee State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Shawnee State'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Siena Heights', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Siena Heights'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Sonoma State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Sonoma State'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'South Carolina State Bulldogs', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'S.C. St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'South Dakota Coyotes', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'South Dakota'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'South Dakota Mines', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'South Dakota Mines'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'South Dakota State Jackrabbits', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'South Dakota St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Southeast Missouri State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Southeast Missouri St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Southeast Missouri State Redhawks', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Southeast Missouri St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Southern Oregon', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Southern Oregon'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Southern Univ.', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Southern Univ.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Southern Virginia', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Southern Virginia'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Southern W.', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Southern W.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Southern-New O.', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Southern-New O.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Southwest Adventist', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Southwest Adventist'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Southwest Minnesota State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Southwest Minnesota State'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Southwest Mustangs', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Southwest Mustangs'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Southwestern Adventist Knights', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Southwestern Adventist'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Southwestern Christian', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Southwestern Christian'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Southwestern Oklahoma', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Southwestern Oklahoma'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Spalding', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Spalding'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Spartanburg', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Spartanburg'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Spring Hill', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Spring Hill'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Springfield Pride', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Springfield Pride'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'St. Ambrose', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'St. Ambrose'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'St. Andrews', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'St. Andrews'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'St. Augustine', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'St. Augustine'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'St. Elizabeth', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'St. Elizabeth'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'St. Francis (ILL)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'St. Francis (ILL)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'St. Francis (PA)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'St. Francis (PA)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'St. John''s (N.Y.)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'St. John''s (N.Y.)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'St. Joseph''s (Brooklyn)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'St. Joseph''s (Brooklyn)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'St. Joseph''s (NY-LI)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'St. Joseph''s (NY-LI)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'St. Louis Billikens', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'St. Louis Billikens'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'St. Louis College of Pharmacy', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'St. Louis College of Pharmacy'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'St. Mary''s (MD)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'St. Mary''s (MD)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'St. Mary''s (MN)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'St. Mary''s (MN)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'St. Marys (CA)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'St. Marys (CA)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'St. Norbert', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'St. Norbert'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'St. Peters', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'St. Peters'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'St. Thomas (Minn.)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'St. Thomas (Minn.)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'St. Thomas (TX)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'St. Thomas (TX)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'St. Thomas (TX) Celts', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'St. Thomas'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'St. Thomas-Minnesota Tommies', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'St. Thomas (MN) Tommies'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'St. Vincent', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'St. Vincent'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'St. Xavier', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'St. Xavier'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Stanford Cardinal', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Stanford'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Stanton', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Stanton'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Sterling College', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Sterling College'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Stetson Hatters', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Stetson'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Steubenville', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Steubenville'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Sul Ross State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Sul Ross State'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Suny Maritime', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Suny Maritime'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Suny Oneonta', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Suny Oneonta'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'TX A&M Commerce', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'TX A&M Commerce'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Tabor', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Tabor'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Talladega', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Talladega'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Tarleton', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Tarleton'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Taylor', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Taylor'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Texas A&M SA Jaguars', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Texas A&M SA Jaguars'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Texas A&M-CC', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Texas A&M-CC'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Texas A&M-Kingsville', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Texas A&M-Kingsville'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Texas College', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Texas College'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Texas Dallas', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Texas Dallas'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Texas Lutheran', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Texas Lutheran'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Texas Texarkana Eagles', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Texas Texarkana Eagles'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Texas Wesleyan', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Texas Wesleyan'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Texas-Permian Basin', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Texas-Permian Basin'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Texas-Tyler Patriots', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Texas-Tyler Patriots'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Thomas (ME) Terriers', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Thomas (ME)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Thomas College', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Thomas College'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Thomas Univ.', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Thomas Univ.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Tiffin', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Tiffin'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Toccoa Falls Eagles', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Toccoa Falls'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Trevecca Nazarene', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Trevecca Nazarene'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Trinity (FL)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Trinity (FL)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Trinity (IL)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Trinity (IL)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Trinity Baptist', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Trinity Baptist'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Trinity of Texas', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Trinity of Texas'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Truett-McConnell Bears', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Truett-McConnell'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Truman State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Truman State'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Tusculum', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Tusculum'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'UALR', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'UALR'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'UMBC Retrievers', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'UMBC'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'UMass Lowell River Hawks', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'UMass Lowell'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'UNT Dallas Trailblazers', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'North Texas'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'USMMA', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'USMMA'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'UW-Stout', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'UW-Stout'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Union Bulldogs', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Union Bulldogs'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'University of Sciences', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'University of Sciences'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'University of the Cumberlands (KY)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'University of the Cumberlands (KY)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Utah Tech Trailblazers', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Utah Tech'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Utah Valley State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Utah Valley State'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'VA Wesleyan', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'VA Wesleyan'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Valley City State Vikings', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Valley City State Vikings'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Valley Forge', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Valley Forge'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Vanguard Lions', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Vanguard Lions'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Vassar', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Vassar'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Vermont Catamounts', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Vermont'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Vermont Spartans', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Vermont'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Vermont State - Johnson', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Vermont State - Johnson'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Vermont State - RK', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Vermont State - RK'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Virginia-Lynchburg Dragons', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Virginia-Lynchburg'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Virginia-Wise', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Virginia-Wise'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Voorhees', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Voorhees'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Waldorf College', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Waldorf College'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Walla Walla', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Walla Walla'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Warner Pacific', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Warner Pacific'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Warner University', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Warner University'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Warren Wilson', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Warren Wilson'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Washington & Lee', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Washington & Lee'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Washington Adventist', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Washington Adventist'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Washington Adventist Shock', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Washington'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Washington Coll', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Washington Coll'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Washington State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Washington St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Washington State Cougars', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Washington St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Wayland Baptist', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Wayland Baptist'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Webber Int''l', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Webber Int''l'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Weber State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Weber St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Wells College', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Wells College'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Wesleyan Univ.', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Wesleyan Univ.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'West Virginia University', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'West Virginia'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'West Virginia Wesleyan', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'West Virginia Wesleyan'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'West Virginia Wesleyan Bobcats', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'West Virginia'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Westcliff', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Westcliff'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Western Colorado', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Western Colorado'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Western N. M.', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Western N. M.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Western Oregon', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Western Oregon'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Westfield State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Westfield State'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Westminster Blue Jays', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Westminster Blue Jays'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Westminster Titans', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Westminster Titans'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Westminster UT', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Westminster UT'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Westmont Warriors', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Westmont Warriors'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Whittier Poets', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Whittier'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Wilberforce', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Wilberforce'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Wiley', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Wiley'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Wilkes Colonels', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Wilkes Colonels'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Willamette Bearcats', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Willamette'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'William & Mary Tribe', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'William & Mary'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'William Carey', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'William Carey'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'William Jessup', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'William Jessup'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'William Peace', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'William Peace'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'William Woods', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'William Woods'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Wilson College', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Wilson College'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Wisc. Green Bay', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Wisc. Green Bay'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Wisc. Milwaukee', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Wisc. Milwaukee'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Wisconsin Falcons', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Wisconsin'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Wisconsin-Stout Blue Devils', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Wisconsin-Stout'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Wittenberg Tigers', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Wittenberg Tigers'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Worcester State', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Worcester State'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Worcester Tech', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Worcester Tech'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Xavier (LA)', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'Xavier (LA)'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'York', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'York'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'York College', 'espn', 1.0
FROM teams t
WHERE t.canonical_name = 'York College'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Albany Great Danes', 'odds_api', 1.0
FROM teams t
WHERE t.canonical_name = 'Albany'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'American Eagles', 'odds_api', 1.0
FROM teams t
WHERE t.canonical_name = 'American'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Boston Univ. Terriers', 'odds_api', 1.0
FROM teams t
WHERE t.canonical_name = 'Boston U'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Dixie State Trailblazers', 'odds_api', 1.0
FROM teams t
WHERE t.canonical_name = 'Utah Tech'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Eastern Kentucky Colonels', 'odds_api', 1.0
FROM teams t
WHERE t.canonical_name = 'Eastern Kentucky'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'GW Revolutionaries', 'odds_api', 1.0
FROM teams t
WHERE t.canonical_name = 'George Washington'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Hartford Hawks', 'odds_api', 1.0
FROM teams t
WHERE t.canonical_name = 'Hartford'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Houston Baptist Huskies', 'odds_api', 1.0
FROM teams t
WHERE t.canonical_name = 'Houston Christian'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'LIU Brooklyn Blackbirds', 'odds_api', 1.0
FROM teams t
WHERE t.canonical_name = 'LIU'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Mcneese St Mcneese', 'odds_api', 1.0
FROM teams t
WHERE t.canonical_name = 'McNeese'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Navy Midshipmen', 'odds_api', 1.0
FROM teams t
WHERE t.canonical_name = 'Navy'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'South Carolina Upstate Spartans', 'odds_api', 1.0
FROM teams t
WHERE t.canonical_name = 'USC Upstate'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'South Dakota St Jackrabbits', 'odds_api', 1.0
FROM teams t
WHERE t.canonical_name = 'South Dakota St.'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'St. Francis BKN Terriers', 'odds_api', 1.0
FROM teams t
WHERE t.canonical_name = 'St. Francis BKN Terriers'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Texas A&M-Commerce Lions', 'odds_api', 1.0
FROM teams t
WHERE t.canonical_name = 'TX A&M Commerce'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'VMI Keydets', 'odds_api', 1.0
FROM teams t
WHERE t.canonical_name = 'VMI'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'Valparaiso Crusaders', 'odds_api', 1.0
FROM teams t
WHERE t.canonical_name = 'Valparaiso'
ON CONFLICT (alias, source) DO NOTHING;
INSERT INTO team_aliases (team_id, alias, source, confidence)
SELECT t.id, 'West Georgia Wolves', 'odds_api', 1.0
FROM teams t
WHERE t.canonical_name = 'West Georgia'
ON CONFLICT (alias, source) DO NOTHING;

COMMIT;
