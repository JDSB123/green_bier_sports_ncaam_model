-- Backtest runs table
CREATE TABLE IF NOT EXISTS backtests (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Backtest parameters
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    bet_types VARCHAR[] NOT NULL, -- ['spread', 'moneyline', 'total']
    game_periods VARCHAR[] NOT NULL, -- ['1Q', '1H', 'full']
    min_confidence DECIMAL(5,4) DEFAULT 0.0,
    max_risk DECIMAL(10,2) DEFAULT 100.0,

    -- Status and timing
    status VARCHAR(50) DEFAULT 'pending', -- pending, running, completed, failed
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    -- Summary metrics
    total_bets INTEGER DEFAULT 0,
    total_won INTEGER DEFAULT 0,
    total_lost INTEGER DEFAULT 0,
    total_push INTEGER DEFAULT 0,
    total_wagered DECIMAL(12,2) DEFAULT 0.0,
    total_returned DECIMAL(12,2) DEFAULT 0.0,
    net_profit DECIMAL(12,2) DEFAULT 0.0,
    roi DECIMAL(8,4) DEFAULT 0.0,
    win_rate DECIMAL(6,4) DEFAULT 0.0,

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Backtest detailed results by bet type and period
CREATE TABLE IF NOT EXISTS backtest_results (
    id SERIAL PRIMARY KEY,
    backtest_id INTEGER NOT NULL REFERENCES backtests(id) ON DELETE CASCADE,

    -- Bet details
    game_id INTEGER REFERENCES games(id),
    game_date DATE NOT NULL,
    home_team_id INTEGER REFERENCES teams(id),
    away_team_id INTEGER REFERENCES teams(id),

    -- Bet configuration
    bet_type VARCHAR(20) NOT NULL, -- spread, moneyline, total
    game_period VARCHAR(10) NOT NULL, -- 1Q, 1H, full
    bet_side VARCHAR(20), -- home, away, over, under

    -- Prediction and confidence
    predicted_value DECIMAL(6,2),
    confidence DECIMAL(5,4),
    edge DECIMAL(6,4), -- predicted edge over the line

    -- Betting odds and lines
    odds_line DECIMAL(6,2), -- spread or total line
    odds_price INTEGER, -- American odds (-110, +150, etc)

    -- Wager and result
    wager_amount DECIMAL(10,2) NOT NULL,
    actual_result DECIMAL(6,2), -- actual score/margin
    outcome VARCHAR(20) NOT NULL, -- win, loss, push
    payout DECIMAL(10,2) NOT NULL,
    profit DECIMAL(10,2) NOT NULL,

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_backtests_status ON backtests(status);
CREATE INDEX idx_backtests_dates ON backtests(start_date, end_date);
CREATE INDEX idx_backtest_results_backtest_id ON backtest_results(backtest_id);
CREATE INDEX idx_backtest_results_game_date ON backtest_results(game_date);
CREATE INDEX idx_backtest_results_bet_type ON backtest_results(bet_type);
CREATE INDEX idx_backtest_results_game_period ON backtest_results(game_period);
CREATE INDEX idx_backtest_results_outcome ON backtest_results(outcome);

-- Function to update backtest summary after results are inserted
CREATE OR REPLACE FUNCTION update_backtest_summary()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE backtests
    SET
        total_bets = (SELECT COUNT(*) FROM backtest_results WHERE backtest_id = NEW.backtest_id),
        total_won = (SELECT COUNT(*) FROM backtest_results WHERE backtest_id = NEW.backtest_id AND outcome = 'win'),
        total_lost = (SELECT COUNT(*) FROM backtest_results WHERE backtest_id = NEW.backtest_id AND outcome = 'loss'),
        total_push = (SELECT COUNT(*) FROM backtest_results WHERE backtest_id = NEW.backtest_id AND outcome = 'push'),
        total_wagered = (SELECT COALESCE(SUM(wager_amount), 0) FROM backtest_results WHERE backtest_id = NEW.backtest_id),
        total_returned = (SELECT COALESCE(SUM(payout), 0) FROM backtest_results WHERE backtest_id = NEW.backtest_id),
        net_profit = (SELECT COALESCE(SUM(profit), 0) FROM backtest_results WHERE backtest_id = NEW.backtest_id),
        roi = CASE
            WHEN (SELECT SUM(wager_amount) FROM backtest_results WHERE backtest_id = NEW.backtest_id) > 0
            THEN (SELECT SUM(profit) FROM backtest_results WHERE backtest_id = NEW.backtest_id) /
                 (SELECT SUM(wager_amount) FROM backtest_results WHERE backtest_id = NEW.backtest_id)
            ELSE 0
        END,
        win_rate = CASE
            WHEN (SELECT COUNT(*) FROM backtest_results WHERE backtest_id = NEW.backtest_id) > 0
            THEN (SELECT COUNT(*)::DECIMAL FROM backtest_results WHERE backtest_id = NEW.backtest_id AND outcome = 'win') /
                 (SELECT COUNT(*) FROM backtest_results WHERE backtest_id = NEW.backtest_id)
            ELSE 0
        END,
        updated_at = NOW()
    WHERE id = NEW.backtest_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to automatically update backtest summary
CREATE TRIGGER backtest_results_summary_trigger
AFTER INSERT ON backtest_results
FOR EACH ROW
EXECUTE FUNCTION update_backtest_summary();
