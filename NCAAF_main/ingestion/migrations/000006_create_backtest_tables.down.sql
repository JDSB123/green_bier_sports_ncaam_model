-- Drop trigger
DROP TRIGGER IF EXISTS backtest_results_summary_trigger ON backtest_results;

-- Drop function
DROP FUNCTION IF EXISTS update_backtest_summary();

-- Drop indexes
DROP INDEX IF EXISTS idx_backtest_results_outcome;
DROP INDEX IF EXISTS idx_backtest_results_game_period;
DROP INDEX IF EXISTS idx_backtest_results_bet_type;
DROP INDEX IF EXISTS idx_backtest_results_game_date;
DROP INDEX IF EXISTS idx_backtest_results_backtest_id;
DROP INDEX IF EXISTS idx_backtests_dates;
DROP INDEX IF EXISTS idx_backtests_status;

-- Drop tables
DROP TABLE IF EXISTS backtest_results;
DROP TABLE IF EXISTS backtests;
