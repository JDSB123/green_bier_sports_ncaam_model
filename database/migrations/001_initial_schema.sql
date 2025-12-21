-- NCAA Basketball Prediction System v6.0
-- Initial Database Schema
-- PostgreSQL 15 + TimescaleDB

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- TimescaleDB is optional (Azure Database for PostgreSQL may not allow-list it).
-- If it's not available, we fall back to standard Postgres tables.
DO $$
BEGIN
    BEGIN
        CREATE EXTENSION IF NOT EXISTS timescaledb;
        RAISE NOTICE 'TimescaleDB extension enabled';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'TimescaleDB extension not available: %', SQLERRM;
    END;
END$$;

-----------------------------------------------------------
-- CORE TABLES
-----------------------------------------------------------

-- Teams (365 NCAA D1 teams)
CREATE TABLE teams (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    canonical_name  TEXT UNIQUE NOT NULL,
    barttorvik_name TEXT,
    conference      TEXT,
    division        TEXT DEFAULT 'D1',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_teams_canonical ON teams(canonical_name);
CREATE INDEX idx_teams_barttorvik ON teams(barttorvik_name);

-- Team aliases (900+ name variations across sources)
CREATE TABLE team_aliases (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id     UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    alias       TEXT NOT NULL,
    source      TEXT NOT NULL,  -- 'the_odds_api', 'api_basketball', 'espn', 'kaggle', 'barttorvik'
    confidence  FLOAT DEFAULT 1.0,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(alias, source)
);

CREATE INDEX idx_team_aliases_alias ON team_aliases(LOWER(alias));
CREATE INDEX idx_team_aliases_team ON team_aliases(team_id);
CREATE INDEX idx_team_aliases_source ON team_aliases(source);

-- Team ratings (daily Barttorvik snapshots)
CREATE TABLE team_ratings (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id         UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    rating_date     DATE NOT NULL,

    -- Barttorvik efficiency ratings
    adj_o           DECIMAL(6,2),      -- Adjusted offensive efficiency (pts per 100 possessions)
    adj_d           DECIMAL(6,2),      -- Adjusted defensive efficiency (pts per 100 possessions)
    tempo           DECIMAL(5,2),      -- Possessions per 40 minutes
    net_rating      DECIMAL(6,2),      -- adj_o - adj_d (calculated)

    -- Rankings
    torvik_rank     INTEGER,

    -- Record
    wins            INTEGER DEFAULT 0,
    losses          INTEGER DEFAULT 0,
    games_played    INTEGER DEFAULT 0,

    -- Metadata
    source_url      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(team_id, rating_date)
);

CREATE INDEX idx_team_ratings_date ON team_ratings(rating_date DESC);
CREATE INDEX idx_team_ratings_team_date ON team_ratings(team_id, rating_date DESC);

-- Games
CREATE TABLE games (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_id     TEXT,              -- The Odds API event ID

    -- Teams
    home_team_id    UUID NOT NULL REFERENCES teams(id),
    away_team_id    UUID NOT NULL REFERENCES teams(id),

    -- Timing
    commence_time   TIMESTAMPTZ NOT NULL,

    -- Venue
    venue           TEXT,
    is_neutral      BOOLEAN DEFAULT FALSE,

    -- Status: scheduled, live, completed, cancelled, postponed
    status          TEXT DEFAULT 'scheduled',

    -- Full game scores
    home_score      INTEGER,
    away_score      INTEGER,

    -- First half scores
    home_score_1h   INTEGER,
    away_score_1h   INTEGER,

    -- Metadata
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_games_commence ON games(commence_time DESC);
CREATE INDEX idx_games_status ON games(status);
CREATE INDEX idx_games_external ON games(external_id);
CREATE INDEX idx_games_teams_date ON games(home_team_id, away_team_id, commence_time);
ALTER TABLE games
    ADD CONSTRAINT games_external_id_key UNIQUE (external_id);

-----------------------------------------------------------
-- PREDICTIONS
-----------------------------------------------------------

-- Predictions
CREATE TABLE predictions (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    game_id                 UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    model_version           TEXT NOT NULL,

    -- Full game predictions
    predicted_spread        DECIMAL(5,2),      -- Home team perspective (negative = home favored)
    predicted_total         DECIMAL(5,2),
    predicted_home_score    DECIMAL(5,2),
    predicted_away_score    DECIMAL(5,2),
    spread_confidence       DECIMAL(4,3),      -- 0.0 to 1.0
    total_confidence        DECIMAL(4,3),

    -- First half predictions
    predicted_spread_1h     DECIMAL(5,2),
    predicted_total_1h      DECIMAL(5,2),
    predicted_home_score_1h DECIMAL(5,2),
    predicted_away_score_1h DECIMAL(5,2),
    spread_confidence_1h    DECIMAL(4,3),
    total_confidence_1h     DECIMAL(4,3),

    -- Moneyline (American odds)
    predicted_home_ml       INTEGER,
    predicted_away_ml       INTEGER,
    predicted_home_ml_1h    INTEGER,
    predicted_away_ml_1h    INTEGER,

    -- Market comparison (at prediction time)
    market_spread           DECIMAL(5,2),
    market_total            DECIMAL(5,2),
    market_spread_1h        DECIMAL(5,2),
    market_total_1h         DECIMAL(5,2),

    -- Edges (model - market)
    spread_edge             DECIMAL(5,2),
    total_edge              DECIMAL(5,2),
    spread_edge_1h          DECIMAL(5,2),
    total_edge_1h           DECIMAL(5,2),

    -- Feature snapshot for reproducibility
    features_json           JSONB,

    -- Metadata
    created_at              TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(game_id, model_version)
);

CREATE INDEX idx_predictions_game ON predictions(game_id);
CREATE INDEX idx_predictions_created ON predictions(created_at DESC);
CREATE INDEX idx_predictions_model ON predictions(model_version);

-- Betting recommendations
CREATE TABLE betting_recommendations (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    prediction_id       UUID NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
    game_id             UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,

    -- Bet details
    bet_type            TEXT NOT NULL,      -- 'SPREAD', 'TOTAL', 'SPREAD_1H', 'TOTAL_1H', 'ML', 'ML_1H'
    pick                TEXT NOT NULL,      -- 'HOME', 'AWAY', 'OVER', 'UNDER'
    line                DECIMAL(5,2),       -- The line at recommendation time

    -- Edge metrics
    edge                DECIMAL(5,2),       -- Points of edge
    confidence          DECIMAL(4,3),       -- 0.0 to 1.0
    ev_percent          DECIMAL(6,3),       -- Expected value %
    kelly_fraction      DECIMAL(5,4),       -- Kelly criterion bet size
    recommended_units   DECIMAL(4,2),       -- Recommended bet units

    -- Bet tier: 'standard' (1-2 units), 'medium' (2-3 units), 'max' (3+ units)
    bet_tier            TEXT DEFAULT 'standard',

    -- Sharp alignment
    sharp_line          DECIMAL(5,2),       -- Pinnacle/Circa line
    steam_aligned       BOOLEAN,            -- Moving same direction as sharps

    -- Outcome tracking
    status              TEXT DEFAULT 'pending',  -- pending, placed, won, lost, push, void
    actual_result       TEXT,               -- Actual outcome description
    closing_line        DECIMAL(5,2),       -- Line at game start (for CLV)
    clv                 DECIMAL(5,2),       -- Closing Line Value
    pnl                 DECIMAL(10,2),      -- Profit/Loss in units

    -- Metadata
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    settled_at          TIMESTAMPTZ
);

CREATE INDEX idx_recommendations_status ON betting_recommendations(status);
CREATE INDEX idx_recommendations_created ON betting_recommendations(created_at DESC);
CREATE INDEX idx_recommendations_bet_type ON betting_recommendations(bet_type);
CREATE INDEX idx_recommendations_game ON betting_recommendations(game_id);

-----------------------------------------------------------
-- TIMESCALEDB HYPERTABLES (Time-Series Data)
-----------------------------------------------------------

-- Odds snapshots (time-series odds history)
CREATE TABLE odds_snapshots (
    time            TIMESTAMPTZ NOT NULL,
    game_id         UUID NOT NULL,
    bookmaker       TEXT NOT NULL,
    market_type     TEXT NOT NULL,      -- 'spread', 'total', 'moneyline'
    period          TEXT NOT NULL,      -- 'full', 'first_half'

    -- Lines
    home_line       DECIMAL(5,2),       -- Spread or ML odds
    away_line       DECIMAL(5,2),
    total_line      DECIMAL(5,2),       -- For totals

    -- Prices (American odds)
    home_price      INTEGER,
    away_price      INTEGER,
    over_price      INTEGER,
    under_price     INTEGER,

    PRIMARY KEY (time, game_id, bookmaker, market_type, period)
);

-- Convert to TimescaleDB hypertable
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable(
            'odds_snapshots',
            'time',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists => TRUE
        );
    ELSE
        RAISE NOTICE 'TimescaleDB not installed; leaving odds_snapshots as a regular table';
    END IF;
END$$;

CREATE INDEX idx_odds_game ON odds_snapshots(game_id, time DESC);
CREATE INDEX idx_odds_bookmaker ON odds_snapshots(bookmaker);

-- Line movement events
CREATE TABLE line_movement_events (
    time            TIMESTAMPTZ NOT NULL,
    game_id         UUID NOT NULL,
    market_type     TEXT NOT NULL,
    period          TEXT NOT NULL,
    bookmaker       TEXT NOT NULL,

    old_line        DECIMAL(5,2),
    new_line        DECIMAL(5,2),
    movement        DECIMAL(5,2),       -- new_line - old_line

    -- Steam move detection
    is_steam_move   BOOLEAN DEFAULT FALSE,
    move_magnitude  TEXT,               -- 'small' (<0.5), 'medium' (0.5-1.5), 'large' (>1.5)

    PRIMARY KEY (time, game_id, market_type, period, bookmaker)
);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable(
            'line_movement_events',
            'time',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists => TRUE
        );
    ELSE
        RAISE NOTICE 'TimescaleDB not installed; leaving line_movement_events as a regular table';
    END IF;
END$$;

CREATE INDEX idx_line_movement_game ON line_movement_events(game_id, time DESC);
CREATE INDEX idx_line_movement_steam ON line_movement_events(is_steam_move) WHERE is_steam_move = TRUE;

-- Model performance tracking
CREATE TABLE model_performance (
    time            TIMESTAMPTZ NOT NULL,
    model_version   TEXT NOT NULL,
    metric_name     TEXT NOT NULL,      -- 'spread_mae', 'total_mae', 'roi_7d', 'clv_rate', etc.
    metric_value    DECIMAL(10,4),
    sample_size     INTEGER,

    PRIMARY KEY (time, model_version, metric_name)
);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable(
            'model_performance',
            'time',
            chunk_time_interval => INTERVAL '7 days',
            if_not_exists => TRUE
        );
    ELSE
        RAISE NOTICE 'TimescaleDB not installed; leaving model_performance as a regular table';
    END IF;
END$$;

-----------------------------------------------------------
-- BACKTESTING
-----------------------------------------------------------

-- Backtest runs
CREATE TABLE backtest_runs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_version   TEXT NOT NULL,
    config_json     JSONB NOT NULL,     -- Model config snapshot

    -- Date range
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,

    -- Sample sizes
    total_games     INTEGER,
    games_with_edge INTEGER,

    -- Full game spread metrics
    spread_mae          DECIMAL(6,3),
    spread_bets         INTEGER,
    spread_wins         INTEGER,
    spread_losses       INTEGER,
    spread_pushes       INTEGER,
    spread_roi          DECIMAL(6,3),
    spread_clv_avg      DECIMAL(5,2),
    spread_clv_positive_rate DECIMAL(5,3),

    -- Full game total metrics
    total_mae           DECIMAL(6,3),
    total_bets          INTEGER,
    total_wins          INTEGER,
    total_losses        INTEGER,
    total_pushes        INTEGER,
    total_roi           DECIMAL(6,3),
    total_clv_avg       DECIMAL(5,2),
    total_clv_positive_rate DECIMAL(5,3),

    -- First half spread metrics
    spread_1h_mae       DECIMAL(6,3),
    spread_1h_bets      INTEGER,
    spread_1h_roi       DECIMAL(6,3),
    spread_1h_clv_avg   DECIMAL(5,2),

    -- First half total metrics
    total_1h_mae        DECIMAL(6,3),
    total_1h_bets       INTEGER,
    total_1h_roi        DECIMAL(6,3),
    total_1h_clv_avg    DECIMAL(5,2),

    -- Overall metrics
    overall_roi         DECIMAL(6,3),
    overall_clv_avg     DECIMAL(5,2),
    sharpe_ratio        DECIMAL(5,3),
    max_drawdown        DECIMAL(6,3),

    -- Metadata
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    duration_seconds    INTEGER
);

CREATE INDEX idx_backtest_model ON backtest_runs(model_version);
CREATE INDEX idx_backtest_created ON backtest_runs(created_at DESC);

-----------------------------------------------------------
-- CONTINUOUS AGGREGATES (Materialized Views)
-----------------------------------------------------------

-- Consensus odds (5-minute buckets)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_matviews
            WHERE schemaname = 'public' AND matviewname = 'odds_consensus'
        ) THEN
            EXECUTE $sql$
                CREATE MATERIALIZED VIEW odds_consensus
                WITH (timescaledb.continuous) AS
                SELECT
                    time_bucket('5 minutes', time) AS bucket,
                    game_id,
                    market_type,
                    period,
                    AVG(home_line) AS consensus_spread,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY home_line) AS median_spread,
                    AVG(total_line) AS consensus_total,
                    MIN(home_line) AS min_spread,
                    MAX(home_line) AS max_spread,
                    COUNT(DISTINCT bookmaker) AS book_count
                FROM odds_snapshots
                GROUP BY bucket, game_id, market_type, period
                WITH NO DATA
            $sql$;
        END IF;

        BEGIN
            PERFORM add_continuous_aggregate_policy(
                'odds_consensus',
                start_offset => INTERVAL '1 hour',
                end_offset => INTERVAL '5 minutes',
                schedule_interval => INTERVAL '5 minutes'
            );
        EXCEPTION WHEN OTHERS THEN
            -- Policy may already exist; ignore
            RAISE NOTICE 'Skipping add_continuous_aggregate_policy(odds_consensus): %', SQLERRM;
        END;
    ELSE
        RAISE NOTICE 'TimescaleDB not installed; skipping continuous aggregate odds_consensus';
    END IF;
END$$;

-----------------------------------------------------------
-- FUNCTIONS
-----------------------------------------------------------

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_teams_updated_at
    BEFORE UPDATE ON teams
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trigger_games_updated_at
    BEFORE UPDATE ON games
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Calculate net rating on insert/update
CREATE OR REPLACE FUNCTION calculate_net_rating()
RETURNS TRIGGER AS $$
BEGIN
    NEW.net_rating = NEW.adj_o - NEW.adj_d;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_team_ratings_net
    BEFORE INSERT OR UPDATE ON team_ratings
    FOR EACH ROW EXECUTE FUNCTION calculate_net_rating();
