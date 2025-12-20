-- Add CLV (Closing Line Value) tracking columns to backtest_results
-- CLV is the gold standard for measuring betting edge

-- Add CLV columns to backtest_results
ALTER TABLE backtest_results 
ADD COLUMN IF NOT EXISTS opening_line DECIMAL(6,2),
ADD COLUMN IF NOT EXISTS closing_line DECIMAL(6,2),
ADD COLUMN IF NOT EXISTS bet_line DECIMAL(6,2),
ADD COLUMN IF NOT EXISTS clv DECIMAL(6,4);

-- Add CLV summary columns to backtests table
ALTER TABLE backtests
ADD COLUMN IF NOT EXISTS avg_clv DECIMAL(8,4) DEFAULT 0.0,
ADD COLUMN IF NOT EXISTS clv_positive_rate DECIMAL(6,4) DEFAULT 0.0,
ADD COLUMN IF NOT EXISTS beat_closing_rate DECIMAL(6,4) DEFAULT 0.0;

-- Create index for CLV analysis
CREATE INDEX IF NOT EXISTS idx_backtest_results_clv ON backtest_results(clv) WHERE clv IS NOT NULL;

-- Add model performance metrics table for regression testing
CREATE TABLE IF NOT EXISTS model_performance_history (
    id SERIAL PRIMARY KEY,
    backtest_id INTEGER REFERENCES backtests(id),
    model_version VARCHAR(50),
    model_type VARCHAR(50), -- 'baseline', 'enhanced', 'ensemble'
    
    -- Core metrics
    roi DECIMAL(8,4),
    win_rate DECIMAL(6,4),
    sharpe_ratio DECIMAL(8,4),
    max_drawdown DECIMAL(6,4),
    
    -- CLV metrics
    avg_clv DECIMAL(8,4),
    clv_positive_rate DECIMAL(6,4),
    beat_closing_rate DECIMAL(6,4),
    
    -- Prediction accuracy
    mae_margin DECIMAL(6,2),
    mae_total DECIMAL(6,2),
    
    -- Sample info
    total_bets INTEGER,
    total_games INTEGER,
    start_date DATE,
    end_date DATE,
    
    -- Walk-forward validation
    is_walk_forward BOOLEAN DEFAULT FALSE,
    training_cutoff_date DATE,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_model_performance_model_type ON model_performance_history(model_type);
CREATE INDEX IF NOT EXISTS idx_model_performance_created_at ON model_performance_history(created_at);

-- Function to update CLV metrics in backtests after results are inserted
CREATE OR REPLACE FUNCTION update_backtest_clv_summary()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE backtests
    SET
        avg_clv = (
            SELECT AVG(clv) FROM backtest_results 
            WHERE backtest_id = NEW.backtest_id AND clv IS NOT NULL
        ),
        clv_positive_rate = (
            SELECT COUNT(*)::DECIMAL / NULLIF(COUNT(*), 0)
            FROM backtest_results 
            WHERE backtest_id = NEW.backtest_id AND clv IS NOT NULL AND clv > 0
        ),
        updated_at = NOW()
    WHERE id = NEW.backtest_id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add trigger for CLV summary updates
DROP TRIGGER IF EXISTS backtest_clv_summary_trigger ON backtest_results;
CREATE TRIGGER backtest_clv_summary_trigger
AFTER INSERT OR UPDATE ON backtest_results
FOR EACH ROW
WHEN (NEW.clv IS NOT NULL)
EXECUTE FUNCTION update_backtest_clv_summary();

COMMENT ON COLUMN backtest_results.clv IS 'Closing Line Value: positive = got better line than closing (real edge indicator)';
COMMENT ON TABLE model_performance_history IS 'Historical model performance for regression testing and trend analysis';
