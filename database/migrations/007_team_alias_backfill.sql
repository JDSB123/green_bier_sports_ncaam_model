-- 007_team_alias_backfill.sql
-- 
-- Harden team alias mappings for The Odds API variants that previously
-- created unrated duplicate teams. This migration:
--   1) Repoints all aliases from the duplicate teams to the rated
--      canonical teams.
--   2) Repoints any games that reference the duplicate team IDs to
--      the rated canonical team IDs.
--
-- This makes the team-matching system fully repeatable for these
-- variants and prevents "missing ratings" issues in predictions.

DO $$
BEGIN
    -- Mapping of problematic canonical names (created by odds ingestion)
    -- to the correct rated canonical team names used by Barttorvik.
    --
    -- LEFT side  = existing unrated canonical in `teams`
    -- RIGHT side = rated canonical in `teams` / `team_ratings`

    -- 1) Repoint aliases from unrated teams to rated canonical teams
    WITH mapping(old_name, new_name) AS (
        VALUES
            ('Coppin St. Eagles',          'Coppin St.'),
            ('Navy Midshipmen',            'Navy'),
            ('Hampton Pirates',            'Hampton'),
            ('Grambling St. Tigers',       'Grambling St.'),
            ('La Salle Explorers',         'La Salle'),
            ('High Point Panthers',        'High Point'),
            ('Miss Valley St. Delta Devils','Mississippi Valley St.'),
            ('Florida St. Seminoles',      'Florida St.'),
            ('Norfolk St. Spartans',       'Norfolk St.'),
            ('Jackson St. Tigers',         'Jackson St.'),
            ('SE Louisiana Lions',         'Southeastern Louisiana'),
            ('Alcorn St. Braves',          'Alcorn St.'),
            ('Florida A&M Rattlers',       'Florida A&M'),
            ('Tarleton St. Texans',        'Tarleton St.'),
            ('North Alabama Lions',        'North Alabama'),
            ('Morgan St. Bears',           'Morgan St.'),
            ('California Golden Bears',    'California')
    ),
    ids AS (
        SELECT 
            o.id AS old_id,
            n.id AS new_id
        FROM mapping m
        JOIN teams o ON o.canonical_name = m.old_name
        JOIN teams n ON n.canonical_name = m.new_name
    )
    UPDATE team_aliases ta
    SET team_id = ids.new_id
    FROM ids
    WHERE ta.team_id = ids.old_id;

    -- 2) Repoint any games where the duplicate team appears as home.
    WITH mapping(old_name, new_name) AS (
        VALUES
            ('Coppin St. Eagles',          'Coppin St.'),
            ('Navy Midshipmen',            'Navy'),
            ('Hampton Pirates',            'Hampton'),
            ('Grambling St. Tigers',       'Grambling St.'),
            ('La Salle Explorers',         'La Salle'),
            ('High Point Panthers',        'High Point'),
            ('Miss Valley St. Delta Devils','Mississippi Valley St.'),
            ('Florida St. Seminoles',      'Florida St.'),
            ('Norfolk St. Spartans',       'Norfolk St.'),
            ('Jackson St. Tigers',         'Jackson St.'),
            ('SE Louisiana Lions',         'Southeastern Louisiana'),
            ('Alcorn St. Braves',          'Alcorn St.'),
            ('Florida A&M Rattlers',       'Florida A&M'),
            ('Tarleton St. Texans',        'Tarleton St.'),
            ('North Alabama Lions',        'North Alabama'),
            ('Morgan St. Bears',           'Morgan St.'),
            ('California Golden Bears',    'California')
    ),
    ids AS (
        SELECT 
            o.id AS old_id,
            n.id AS new_id
        FROM mapping m
        JOIN teams o ON o.canonical_name = m.old_name
        JOIN teams n ON n.canonical_name = m.new_name
    )
    UPDATE games g
    SET home_team_id = ids.new_id
    FROM ids
    WHERE g.home_team_id = ids.old_id;

    -- 3) Repoint any games where the duplicate team appears as away.
    WITH mapping(old_name, new_name) AS (
        VALUES
            ('Coppin St. Eagles',          'Coppin St.'),
            ('Navy Midshipmen',            'Navy'),
            ('Hampton Pirates',            'Hampton'),
            ('Grambling St. Tigers',       'Grambling St.'),
            ('La Salle Explorers',         'La Salle'),
            ('High Point Panthers',        'High Point'),
            ('Miss Valley St. Delta Devils','Mississippi Valley St.'),
            ('Florida St. Seminoles',      'Florida St.'),
            ('Norfolk St. Spartans',       'Norfolk St.'),
            ('Jackson St. Tigers',         'Jackson St.'),
            ('SE Louisiana Lions',         'Southeastern Louisiana'),
            ('Alcorn St. Braves',          'Alcorn St.'),
            ('Florida A&M Rattlers',       'Florida A&M'),
            ('Tarleton St. Texans',        'Tarleton St.'),
            ('North Alabama Lions',        'North Alabama'),
            ('Morgan St. Bears',           'Morgan St.'),
            ('California Golden Bears',    'California')
    ),
    ids AS (
        SELECT 
            o.id AS old_id,
            n.id AS new_id
        FROM mapping m
        JOIN teams o ON o.canonical_name = m.old_name
        JOIN teams n ON n.canonical_name = m.new_name
    )
    UPDATE games g2
    SET away_team_id = ids.new_id
    FROM ids
    WHERE g2.away_team_id = ids.old_id;
END;
$$;

