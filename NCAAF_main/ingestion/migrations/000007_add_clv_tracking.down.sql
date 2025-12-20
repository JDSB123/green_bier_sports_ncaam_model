-- Rollback CLV tracking additions

-- Remove trigger
DROP TRIGGER IF EXISTS backtest_clv_summary_trigger ON backtest_results;
DROP FUNCTION IF EXISTS update_backtest_clv_summary();

-- Remove model performance history table
DROP TABLE IF EXISTS model_performance_history;

-- Remove CLV columns from backtests
ALTER TABLE backtests
DROP COLUMN IF EXISTS avg_clv,
DROP COLUMN IF EXISTS clv_positive_rate,
DROP COLUMN IF EXISTS beat_closing_rate;

-- Remove CLV columns from backtest_results
DROP INDEX IF EXISTS idx_backtest_results_clv;
ALTER TABLE backtest_results 
DROP COLUMN IF EXISTS opening_line,
DROP COLUMN IF EXISTS closing_line,
DROP COLUMN IF EXISTS bet_line,
DROP COLUMN IF EXISTS clv;
