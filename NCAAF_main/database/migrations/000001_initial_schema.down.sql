-- Rollback migration for initial schema

-- Drop views first
DROP VIEW IF EXISTS game_results_with_predictions;
DROP VIEW IF EXISTS latest_odds;
DROP VIEW IF EXISTS active_games;

-- Drop triggers
DROP TRIGGER IF EXISTS update_box_scores_updated_at ON box_scores;
DROP TRIGGER IF EXISTS update_odds_updated_at ON odds;
DROP TRIGGER IF EXISTS update_team_season_stats_updated_at ON team_season_stats;
DROP TRIGGER IF EXISTS update_games_updated_at ON games;
DROP TRIGGER IF EXISTS update_teams_updated_at ON teams;

-- Drop function
DROP FUNCTION IF EXISTS update_updated_at_column();

-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS bets;
DROP TABLE IF EXISTS predictions;
DROP TABLE IF EXISTS box_scores;
DROP TABLE IF EXISTS line_movement;
DROP TABLE IF EXISTS odds;
DROP TABLE IF EXISTS team_season_stats;
DROP TABLE IF EXISTS games;
DROP TABLE IF EXISTS stadiums;
DROP TABLE IF EXISTS teams;

-- Drop extension
DROP EXTENSION IF EXISTS "uuid-ossp";
