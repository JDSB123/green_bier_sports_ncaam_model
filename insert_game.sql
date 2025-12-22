
WITH inserted_game AS (
    INSERT INTO games (id, home_team_id, away_team_id, commence_time, status, is_neutral, created_at, updated_at, external_id)
    VALUES (
        gen_random_uuid(),
        '190ba13e-676d-4eff-8cb1-c07af66cffb5', -- Nebraska
        '38524426-d6d6-4105-bcf6-22d31d5b05c9', -- North Dakota
        '2025-12-22 01:00:00+00', 
        'scheduled',
        false,
        NOW(),
        NOW(),
        'manual_insert_nebraska_north_dakota_20251221'
    )
    RETURNING id
)
INSERT INTO odds_snapshots (
    game_id, market_type, period, bookmaker, 
    home_line, away_line, home_price, away_price, 
    total_line, over_price, under_price, time
)
SELECT 
    id, 'spreads', 'full', 'pinnacle',
    -30.5, 30.5, -110, -110, 
    NULL, NULL, NULL, NOW()
FROM inserted_game
UNION ALL
SELECT 
    id, 'totals', 'full', 'pinnacle',
    NULL, NULL, NULL, NULL,
    148.5, -110, -110, NOW()
FROM inserted_game;
