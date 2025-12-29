-- Complete remaining schema (skipping teams, team_ratings, team_aliases which exist)

-- Games
CREATE TABLE IF NOT EXISTS games (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_id     TEXT,
    home_team_id    UUID NOT NULL REFERENCES teams(id),
    away_team_id    UUID NOT NULL REFERENCES teams(id),
    commence_time   TIMESTAMPTZ NOT NULL,
    venue           TEXT,
    is_neutral      BOOLEAN DEFAULT FALSE,
    status          TEXT DEFAULT 'scheduled',
    home_score      INTEGER,
    away_score      INTEGER,
    home_score_1h   INTEGER,
    away_score_1h   INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_games_commence ON games(commence_time DESC);
CREATE INDEX IF NOT EXISTS idx_games_status ON games(status);
CREATE INDEX IF NOT EXISTS idx_games_external ON games(external_id);
CREATE INDEX IF NOT EXISTS idx_games_teams_date ON games(home_team_id, away_team_id, commence_time);
-- Postgres does not support `ADD CONSTRAINT IF NOT EXISTS`; make it idempotent.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'games_external_id_key'
          AND conrelid = 'games'::regclass
    ) THEN
        ALTER TABLE games
            ADD CONSTRAINT games_external_id_key UNIQUE (external_id);
    END IF;
END $$;

-- Predictions
CREATE TABLE IF NOT EXISTS predictions (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    game_id                 UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    model_version           TEXT NOT NULL,
    predicted_spread        DECIMAL(5,2),
    predicted_total         DECIMAL(5,2),
    predicted_home_score    DECIMAL(5,2),
    predicted_away_score    DECIMAL(5,2),
    spread_confidence       DECIMAL(4,3),
    total_confidence        DECIMAL(4,3),
    predicted_spread_1h     DECIMAL(5,2),
    predicted_total_1h      DECIMAL(5,2),
    predicted_home_score_1h DECIMAL(5,2),
    predicted_away_score_1h DECIMAL(5,2),
    spread_confidence_1h    DECIMAL(4,3),
    total_confidence_1h     DECIMAL(4,3),
    market_spread           DECIMAL(5,2),
    market_total            DECIMAL(5,2),
    market_spread_1h        DECIMAL(5,2),
    market_total_1h         DECIMAL(5,2),
    spread_edge             DECIMAL(5,2),
    total_edge              DECIMAL(5,2),
    spread_edge_1h          DECIMAL(5,2),
    total_edge_1h           DECIMAL(5,2),
    features_json           JSONB,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(game_id, model_version)
);

CREATE INDEX IF NOT EXISTS idx_predictions_game ON predictions(game_id);
CREATE INDEX IF NOT EXISTS idx_predictions_created ON predictions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_model ON predictions(model_version);

-- Betting recommendations
CREATE TABLE IF NOT EXISTS betting_recommendations (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    prediction_id       UUID NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
    game_id             UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    bet_type            TEXT NOT NULL,
    pick                TEXT NOT NULL,
    line                DECIMAL(5,2),
    edge                DECIMAL(5,2),
    confidence          DECIMAL(4,3),
    ev_percent          DECIMAL(6,3),
    kelly_fraction      DECIMAL(5,4),
    recommended_units   DECIMAL(4,2),
    bet_tier            TEXT DEFAULT 'standard',
    sharp_line          DECIMAL(5,2),
    steam_aligned       BOOLEAN,
    status              TEXT DEFAULT 'pending',
    actual_result       TEXT,
    closing_line        DECIMAL(5,2),
    clv                 DECIMAL(5,2),
    pnl                 DECIMAL(10,2),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    settled_at          TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_recommendations_prediction ON betting_recommendations(prediction_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_game ON betting_recommendations(game_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_created ON betting_recommendations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_recommendations_status ON betting_recommendations(status);

-- Odds snapshots (time-series)
CREATE TABLE IF NOT EXISTS odds_snapshots (
    time            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    game_id         UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    bookmaker       TEXT NOT NULL,
    market_type     TEXT NOT NULL,
    period          TEXT NOT NULL DEFAULT 'full',
    home_line       DECIMAL(5,2),
    away_line       DECIMAL(5,2),
    total_line      DECIMAL(5,2),
    home_price      INTEGER,
    away_price      INTEGER,
    over_price      INTEGER,
    under_price     INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (time, game_id, bookmaker, market_type, period)
);

CREATE INDEX IF NOT EXISTS idx_odds_bookmaker ON odds_snapshots(bookmaker);
CREATE INDEX IF NOT EXISTS odds_snapshots_time_idx ON odds_snapshots(time DESC);
CREATE INDEX IF NOT EXISTS idx_odds_game_time ON odds_snapshots(game_id, time DESC);

-- Sharp consensus (aggregated sharp lines)
CREATE TABLE IF NOT EXISTS sharp_consensus (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    game_id         UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    calculated_at   TIMESTAMPTZ NOT NULL,
    spread          DECIMAL(5,2),
    spread_std      DECIMAL(5,4),
    total           DECIMAL(5,2),
    total_std       DECIMAL(5,4),
    bookmaker_count INTEGER,
    bookmakers      TEXT[],
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sharp_consensus_game_time ON sharp_consensus(game_id, calculated_at DESC);
CREATE INDEX IF NOT EXISTS idx_sharp_consensus_calculated ON sharp_consensus(calculated_at DESC);

-- Public/Sharp splits (betting percentages)
CREATE TABLE IF NOT EXISTS public_sharp_splits (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    game_id         UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    timestamp       TIMESTAMPTZ NOT NULL,
    
    -- Spread
    spread_public_bets_pct      DECIMAL(5,2),
    spread_public_money_pct     DECIMAL(5,2),
    spread_sharp_bets_pct       DECIMAL(5,2),
    spread_sharp_money_pct      DECIMAL(5,2),
    spread_public_side          TEXT,
    spread_sharp_side           TEXT,
    
    -- Total
    total_public_bets_pct       DECIMAL(5,2),
    total_public_money_pct      DECIMAL(5,2),
    total_sharp_bets_pct        DECIMAL(5,2),
    total_sharp_money_pct       DECIMAL(5,2),
    total_public_side           TEXT,
    total_sharp_side            TEXT,
    source          TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_splits_game_time ON public_sharp_splits(game_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_splits_timestamp ON public_sharp_splits(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_splits_source ON public_sharp_splits(source);

-- Line movement analysis
CREATE TABLE IF NOT EXISTS line_movement_analysis (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    game_id                 UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    analyzed_at             TIMESTAMPTZ NOT NULL,
    
    -- Spread movement
    spread_open             DECIMAL(5,2),
    spread_current          DECIMAL(5,2),
    spread_movement         DECIMAL(5,2),
    spread_sharp_side       TEXT,
    spread_public_side      TEXT,
    spread_reverse_line     BOOLEAN,
    spread_steam_move       BOOLEAN,
    spread_confidence       DECIMAL(4,3),
    
    -- Total movement
    total_open              DECIMAL(5,2),
    total_current           DECIMAL(5,2),
    total_movement          DECIMAL(5,2),
    total_sharp_side        TEXT,
    total_public_side       TEXT,
    total_reverse_line      BOOLEAN,
    total_steam_move        BOOLEAN,
    total_confidence        DECIMAL(4,3),
    
    -- Overall analysis
    overall_sharp_side      TEXT,
    overall_confidence      DECIMAL(4,3),
    
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_line_movement_game_time ON line_movement_analysis(game_id, analyzed_at DESC);
CREATE INDEX IF NOT EXISTS idx_line_movement_confidence ON line_movement_analysis(overall_confidence DESC);
CREATE INDEX IF NOT EXISTS idx_line_movement_steam ON line_movement_analysis(spread_steam_move, total_steam_move);
