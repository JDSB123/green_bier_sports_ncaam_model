-- Add sharp consensus and public/sharp splits tables
-- Run after 001_initial_schema.sql

-- Sharp consensus (computed from sharp bookmakers)
CREATE TABLE sharp_consensus (
    time            TIMESTAMPTZ NOT NULL,
    game_id         UUID NOT NULL,
    market_type     TEXT NOT NULL,      -- 'spreads', 'totals'
    period          TEXT NOT NULL,      -- 'full', 'first_half'

    -- Sharp lines (Pinnacle, Circa, Bookmaker)
    sharp_spread    DECIMAL(5,2),
    sharp_total     DECIMAL(5,2),
    -- Prices
    sharp_spread_price INTEGER,
    sharp_over_price   INTEGER,
    sharp_under_price  INTEGER,

    -- Metadata
    book_count      INTEGER,            -- Number of sharp books with data
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (time, game_id, market_type, period)
);

CREATE INDEX idx_sharp_consensus_game ON sharp_consensus(game_id, time DESC);

-- Public vs Sharp splits (betting percentages)
-- Tracks what % of public bets vs sharp money on each side
CREATE TABLE public_sharp_splits (
    time            TIMESTAMPTZ NOT NULL,
    game_id         UUID NOT NULL,
    market_type     TEXT NOT NULL,      -- 'spreads', 'totals'
    period          TEXT NOT NULL,      -- 'full', 'first_half'

    -- Public betting %
    public_home_pct     DECIMAL(5,2),   -- % of public bets on home
    public_away_pct     DECIMAL(5,2),
    public_over_pct     DECIMAL(5,2),
    public_under_pct    DECIMAL(5,2),

    -- Sharp money %
    sharp_home_pct      DECIMAL(5,2),   -- % of sharp money on home
    sharp_away_pct      DECIMAL(5,2),
    sharp_over_pct      DECIMAL(5,2),
    sharp_under_pct     DECIMAL(5,2),

    -- Bet counts
    public_bet_count    INTEGER,
    sharp_bet_count     INTEGER,

    -- Source (e.g., 'action_network', 'covers', 'pregame')
    source              TEXT,

    PRIMARY KEY (time, game_id, market_type, period, source)
);

CREATE INDEX idx_splits_game ON public_sharp_splits(game_id, time DESC);
CREATE INDEX idx_splits_source ON public_sharp_splits(source);

-- View: Latest sharp consensus per game
CREATE VIEW latest_sharp_consensus AS
SELECT DISTINCT ON (game_id, market_type, period)
    game_id,
    market_type,
    period,
    sharp_spread,
    sharp_total,
    time
FROM sharp_consensus
ORDER BY game_id, market_type, period, time DESC;

-- View: Latest public/sharp splits per game
CREATE VIEW latest_public_sharp_splits AS
SELECT DISTINCT ON (game_id, market_type, period)
    game_id,
    market_type,
    period,
    public_home_pct,
    public_away_pct,
    sharp_home_pct,
    sharp_away_pct,
    public_over_pct,
    public_under_pct,
    sharp_over_pct,
    sharp_under_pct,
    source,
    time
FROM public_sharp_splits
ORDER BY game_id, market_type, period, time DESC;
