-- NCAAF v5.0 Database Schema - Initial Migration
-- PostgreSQL database schema for college football prediction system
-- Following SportsDataIO best practices: store all data locally

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- TEAMS
-- ============================================================================
CREATE TABLE teams (
    id SERIAL PRIMARY KEY,
    team_id INTEGER UNIQUE NOT NULL,  -- SportsDataIO TeamID
    team_code VARCHAR(10) UNIQUE NOT NULL,  -- e.g., 'ALA', 'UGA'
    school_name VARCHAR(255) NOT NULL,  -- e.g., 'Alabama'
    mascot VARCHAR(100),  -- e.g., 'Crimson Tide'
    conference VARCHAR(100),
    division VARCHAR(100),

    -- Talent composite (from recruiting rankings)
    talent_composite DECIMAL(5,3),  -- 0.0-1.0 scale

    -- Location
    city VARCHAR(100),
    state VARCHAR(2),

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_teams_team_code ON teams(team_code);
CREATE INDEX idx_teams_conference ON teams(conference);

-- ============================================================================
-- STADIUMS
-- ============================================================================
CREATE TABLE stadiums (
    id SERIAL PRIMARY KEY,
    stadium_id INTEGER UNIQUE NOT NULL,  -- SportsDataIO StadiumID
    name VARCHAR(255) NOT NULL,
    city VARCHAR(100),
    state VARCHAR(2),
    country VARCHAR(2),
    capacity INTEGER,
    surface VARCHAR(50),  -- e.g., 'Grass', 'FieldTurf'

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- GAMES
-- ============================================================================
CREATE TABLE games (
    id SERIAL PRIMARY KEY,
    game_id INTEGER UNIQUE NOT NULL,  -- SportsDataIO GameID
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,

    -- Teams
    home_team_id INTEGER REFERENCES teams(id) NOT NULL,
    away_team_id INTEGER REFERENCES teams(id) NOT NULL,
    home_team_code VARCHAR(10) NOT NULL,
    away_team_code VARCHAR(10) NOT NULL,

    -- Scheduling
    game_date TIMESTAMP NOT NULL,
    stadium_id INTEGER REFERENCES stadiums(id),

    -- Status
    status VARCHAR(50) NOT NULL,  -- 'Scheduled', 'InProgress', 'Final', 'Postponed', 'Canceled'
    period VARCHAR(20),  -- 'Half', '1st', '2nd', '3rd', '4th', 'OT'
    time_remaining VARCHAR(10),

    -- Scores
    home_score INTEGER,
    away_score INTEGER,

    -- Quarter scores
    home_score_quarter_1 INTEGER,
    home_score_quarter_2 INTEGER,
    home_score_quarter_3 INTEGER,
    home_score_quarter_4 INTEGER,
    home_score_overtime INTEGER,

    away_score_quarter_1 INTEGER,
    away_score_quarter_2 INTEGER,
    away_score_quarter_3 INTEGER,
    away_score_quarter_4 INTEGER,
    away_score_overtime INTEGER,

    -- Derived fields
    total_score INTEGER GENERATED ALWAYS AS (
        COALESCE(home_score, 0) + COALESCE(away_score, 0)
    ) STORED,
    margin INTEGER GENERATED ALWAYS AS (
        COALESCE(home_score, 0) - COALESCE(away_score, 0)
    ) STORED,

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_games_season_week ON games(season, week);
CREATE INDEX idx_games_status ON games(status);
CREATE INDEX idx_games_game_date ON games(game_date);
CREATE INDEX idx_games_home_team ON games(home_team_id);
CREATE INDEX idx_games_away_team ON games(away_team_id);

-- ============================================================================
-- TEAM SEASON STATS
-- ============================================================================
CREATE TABLE team_season_stats (
    id SERIAL PRIMARY KEY,
    team_id INTEGER REFERENCES teams(id) NOT NULL,
    season INTEGER NOT NULL,

    -- Offense
    points_per_game DECIMAL(5,2),
    yards_per_game DECIMAL(6,2),
    pass_yards_per_game DECIMAL(6,2),
    rush_yards_per_game DECIMAL(6,2),
    yards_per_play DECIMAL(5,2),

    -- Defense
    points_allowed_per_game DECIMAL(5,2),
    yards_allowed_per_game DECIMAL(6,2),
    pass_yards_allowed_per_game DECIMAL(6,2),
    rush_yards_allowed_per_game DECIMAL(6,2),
    yards_per_play_allowed DECIMAL(5,2),

    -- Efficiency
    third_down_conversion_pct DECIMAL(5,2),
    fourth_down_conversion_pct DECIMAL(5,2),
    red_zone_scoring_pct DECIMAL(5,2),

    -- Turnovers
    turnovers INTEGER,
    takeaways INTEGER,
    turnover_margin INTEGER,

    -- Special Teams
    punt_return_yards_per_attempt DECIMAL(5,2),
    kick_return_yards_per_attempt DECIMAL(5,2),

    -- QB Stats (aggregated)
    qb_rating DECIMAL(6,2),
    completion_percentage DECIMAL(5,2),
    passing_touchdowns INTEGER,
    interceptions INTEGER,

    -- Record
    wins INTEGER,
    losses INTEGER,

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(team_id, season)
);

CREATE INDEX idx_team_season_stats_team ON team_season_stats(team_id);
CREATE INDEX idx_team_season_stats_season ON team_season_stats(season);

-- ============================================================================
-- ODDS
-- ============================================================================
CREATE TABLE odds (
    id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games(id) NOT NULL,

    -- Sportsbook
    sportsbook_id VARCHAR(10) NOT NULL,  -- e.g., '1105' (Pinnacle)
    sportsbook_name VARCHAR(100),

    -- Market type
    market_type VARCHAR(50) NOT NULL,  -- 'GameLine', 'Total', 'Moneyline', 'TeamTotal'
    period VARCHAR(20) NOT NULL,  -- 'FG' (Full Game), '1H', 'Q1', 'Q2', etc.

    -- Line values
    home_spread DECIMAL(5,2),
    away_spread DECIMAL(5,2),
    over_under DECIMAL(5,2),
    home_moneyline INTEGER,
    away_moneyline INTEGER,
    home_team_total DECIMAL(5,2),
    away_team_total DECIMAL(5,2),

    -- Juice (vig)
    home_spread_juice INTEGER,
    away_spread_juice INTEGER,
    over_juice INTEGER,
    under_juice INTEGER,

    -- Timestamps
    fetched_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_odds_game ON odds(game_id);
CREATE INDEX idx_odds_sportsbook ON odds(sportsbook_id);
CREATE INDEX idx_odds_market_type ON odds(market_type);
CREATE INDEX idx_odds_fetched_at ON odds(fetched_at DESC);

-- ============================================================================
-- LINE MOVEMENT
-- ============================================================================
CREATE TABLE line_movement (
    id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games(id) NOT NULL,

    -- Sportsbook
    sportsbook_id VARCHAR(10) NOT NULL,
    sportsbook_name VARCHAR(100),

    -- Market
    market_type VARCHAR(50) NOT NULL,
    period VARCHAR(20) NOT NULL,

    -- Previous line
    prev_home_spread DECIMAL(5,2),
    prev_away_spread DECIMAL(5,2),
    prev_over_under DECIMAL(5,2),
    prev_home_moneyline INTEGER,
    prev_away_moneyline INTEGER,

    -- New line
    new_home_spread DECIMAL(5,2),
    new_away_spread DECIMAL(5,2),
    new_over_under DECIMAL(5,2),
    new_home_moneyline INTEGER,
    new_away_moneyline INTEGER,

    -- Movement metadata
    movement_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    movement_direction VARCHAR(20),  -- 'toward_home', 'toward_away', 'total_up', 'total_down'
    movement_magnitude DECIMAL(5,2),

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_line_movement_game ON line_movement(game_id);
CREATE INDEX idx_line_movement_timestamp ON line_movement(movement_timestamp DESC);

-- ============================================================================
-- BOX SCORES (Detailed game statistics)
-- ============================================================================
CREATE TABLE box_scores (
    id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games(id) NOT NULL,
    team_id INTEGER REFERENCES teams(id) NOT NULL,

    -- Basic stats
    points INTEGER,
    first_downs INTEGER,
    total_yards INTEGER,
    passing_yards INTEGER,
    rushing_yards INTEGER,
    penalties INTEGER,
    penalty_yards INTEGER,
    turnovers INTEGER,
    fumbles_lost INTEGER,
    interceptions INTEGER,

    -- Possession
    possession_minutes INTEGER,
    possession_seconds INTEGER,

    -- Efficiency
    third_down_attempts INTEGER,
    third_down_conversions INTEGER,
    fourth_down_attempts INTEGER,
    fourth_down_conversions INTEGER,
    red_zone_attempts INTEGER,
    red_zone_conversions INTEGER,

    -- Quarter breakdown (JSON for flexibility)
    quarter_scores JSONB,  -- {Q1: 7, Q2: 14, Q3: 0, Q4: 10}

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(game_id, team_id)
);

CREATE INDEX idx_box_scores_game ON box_scores(game_id);
CREATE INDEX idx_box_scores_team ON box_scores(team_id);

-- ============================================================================
-- PREDICTIONS
-- ============================================================================
CREATE TABLE predictions (
    id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games(id) NOT NULL,

    -- Model info
    model_name VARCHAR(100) NOT NULL,  -- 'xgboost_spread', 'linear_fundamental', etc.
    model_version VARCHAR(50),

    -- Predictions
    predicted_home_score DECIMAL(5,2),
    predicted_away_score DECIMAL(5,2),
    predicted_total DECIMAL(5,2),
    predicted_margin DECIMAL(5,2),  -- positive = home favored

    -- Confidence
    confidence_score DECIMAL(5,4),  -- 0.0-1.0

    -- Market comparison
    consensus_spread DECIMAL(5,2),
    consensus_total DECIMAL(5,2),
    edge_spread DECIMAL(5,2),  -- model prediction - market consensus
    edge_total DECIMAL(5,2),

    -- Recommendation
    recommend_bet BOOLEAN DEFAULT FALSE,
    recommended_bet_type VARCHAR(50),  -- 'spread', 'total', 'moneyline', 'team_total'
    recommended_side VARCHAR(20),  -- 'home', 'away', 'over', 'under'
    recommended_units DECIMAL(3,1),  -- 0.5-2.0

    -- Rationale (JSON)
    rationale JSONB,

    -- Metadata
    predicted_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_predictions_game ON predictions(game_id);
CREATE INDEX idx_predictions_model ON predictions(model_name);
CREATE INDEX idx_predictions_recommend_bet ON predictions(recommend_bet);

-- ============================================================================
-- BET TRACKING (For CLV tracking and performance analysis)
-- ============================================================================
CREATE TABLE bets (
    id SERIAL PRIMARY KEY,
    prediction_id INTEGER REFERENCES predictions(id) NOT NULL,
    game_id INTEGER REFERENCES games(id) NOT NULL,

    -- Bet details
    bet_type VARCHAR(50) NOT NULL,
    side VARCHAR(20) NOT NULL,
    betted_line DECIMAL(5,2),  -- Line at time of bet
    closing_line DECIMAL(5,2),  -- Line at game start
    units DECIMAL(3,1),

    -- Sportsbook
    sportsbook_id VARCHAR(10),
    sportsbook_name VARCHAR(100),

    -- Result
    result VARCHAR(20),  -- 'win', 'loss', 'push', 'pending'
    profit_loss DECIMAL(8,2),

    -- CLV (Closing Line Value)
    clv DECIMAL(5,2),  -- betted_line - closing_line

    -- Metadata
    betted_at TIMESTAMP NOT NULL,
    settled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_bets_game ON bets(game_id);
CREATE INDEX idx_bets_result ON bets(result);
CREATE INDEX idx_bets_betted_at ON bets(betted_at DESC);

-- ============================================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER update_teams_updated_at BEFORE UPDATE ON teams
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_games_updated_at BEFORE UPDATE ON games
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_team_season_stats_updated_at BEFORE UPDATE ON team_season_stats
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_odds_updated_at BEFORE UPDATE ON odds
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_box_scores_updated_at BEFORE UPDATE ON box_scores
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- VIEWS
-- ============================================================================

-- View for active games (games currently in progress)
CREATE OR REPLACE VIEW active_games AS
SELECT g.*,
       ht.school_name AS home_team_name,
       at.school_name AS away_team_name
FROM games g
JOIN teams ht ON g.home_team_id = ht.id
JOIN teams at ON g.away_team_id = at.id
WHERE g.status IN ('InProgress', 'Scheduled')
  AND g.game_date < NOW()
  AND g.status NOT IN ('Final', 'Postponed', 'Canceled');

-- View for latest odds by game
CREATE OR REPLACE VIEW latest_odds AS
SELECT DISTINCT ON (game_id, sportsbook_id, market_type, period)
       *
FROM odds
ORDER BY game_id, sportsbook_id, market_type, period, fetched_at DESC;

-- View for game results with predictions
CREATE OR REPLACE VIEW game_results_with_predictions AS
SELECT
    g.id,
    g.game_id,
    g.season,
    g.week,
    g.home_team_code,
    g.away_team_code,
    g.home_score,
    g.away_score,
    g.total_score,
    g.margin,
    p.predicted_home_score,
    p.predicted_away_score,
    p.predicted_total,
    p.predicted_margin,
    p.edge_spread,
    p.edge_total,
    p.model_name,
    ABS(g.total_score - p.predicted_total) AS total_error,
    ABS(g.margin - p.predicted_margin) AS margin_error
FROM games g
LEFT JOIN predictions p ON g.id = p.game_id
WHERE g.status = 'Final';
