package repository

import (
	"context"
	"fmt"

	"ncaaf_v5/ingestion/internal/models"

	"github.com/jackc/pgx/v5"
	"github.com/rs/zerolog/log"
)

// GameRepository handles game database operations
type GameRepository struct {
	db *Database
}

// Create inserts a new game
func (r *GameRepository) Create(ctx context.Context, game *models.Game) error {
	query := `
		INSERT INTO games (
			game_id, season, week, home_team_id, away_team_id,
			home_team_code, away_team_code, game_date, stadium_id, status,
			period, time_remaining, home_score, away_score,
			home_score_quarter_1, home_score_quarter_2, home_score_quarter_3, home_score_quarter_4, home_score_overtime,
			away_score_quarter_1, away_score_quarter_2, away_score_quarter_3, away_score_quarter_4, away_score_overtime
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24)
		RETURNING id, total_score, margin, created_at, updated_at
	`

	err := r.db.Pool.QueryRow(
		ctx, query,
		game.GameID, game.Season, game.Week, game.HomeTeamID, game.AwayTeamID,
		game.HomeTeamCode, game.AwayTeamCode, game.GameDate, game.StadiumID, game.Status,
		game.Period, game.TimeRemaining, game.HomeScore, game.AwayScore,
		game.HomeScoreQuarter1, game.HomeScoreQuarter2, game.HomeScoreQuarter3, game.HomeScoreQuarter4, game.HomeScoreOvertime,
		game.AwayScoreQuarter1, game.AwayScoreQuarter2, game.AwayScoreQuarter3, game.AwayScoreQuarter4, game.AwayScoreOvertime,
	).Scan(&game.ID, &game.TotalScore, &game.Margin, &game.CreatedAt, &game.UpdatedAt)

	if err != nil {
		return fmt.Errorf("failed to create game: %w", err)
	}

	log.Debug().
		Int("id", game.ID).
		Int("game_id", game.GameID).
		Str("home", game.HomeTeamCode).
		Str("away", game.AwayTeamCode).
		Msg("Game created")

	return nil
}

// Upsert inserts or updates a game
func (r *GameRepository) Upsert(ctx context.Context, game *models.Game) error {
	query := `
		INSERT INTO games (
			game_id, season, week, home_team_id, away_team_id,
			home_team_code, away_team_code, game_date, stadium_id, status,
			period, time_remaining, home_score, away_score,
			home_score_quarter_1, home_score_quarter_2, home_score_quarter_3, home_score_quarter_4, home_score_overtime,
			away_score_quarter_1, away_score_quarter_2, away_score_quarter_3, away_score_quarter_4, away_score_overtime
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24)
		ON CONFLICT (game_id) DO UPDATE SET
			season = EXCLUDED.season,
			week = EXCLUDED.week,
			home_team_id = EXCLUDED.home_team_id,
			away_team_id = EXCLUDED.away_team_id,
			home_team_code = EXCLUDED.home_team_code,
			away_team_code = EXCLUDED.away_team_code,
			game_date = EXCLUDED.game_date,
			stadium_id = EXCLUDED.stadium_id,
			status = EXCLUDED.status,
			period = EXCLUDED.period,
			time_remaining = EXCLUDED.time_remaining,
			home_score = EXCLUDED.home_score,
			away_score = EXCLUDED.away_score,
			home_score_quarter_1 = EXCLUDED.home_score_quarter_1,
			home_score_quarter_2 = EXCLUDED.home_score_quarter_2,
			home_score_quarter_3 = EXCLUDED.home_score_quarter_3,
			home_score_quarter_4 = EXCLUDED.home_score_quarter_4,
			home_score_overtime = EXCLUDED.home_score_overtime,
			away_score_quarter_1 = EXCLUDED.away_score_quarter_1,
			away_score_quarter_2 = EXCLUDED.away_score_quarter_2,
			away_score_quarter_3 = EXCLUDED.away_score_quarter_3,
			away_score_quarter_4 = EXCLUDED.away_score_quarter_4,
			away_score_overtime = EXCLUDED.away_score_overtime,
			updated_at = NOW()
		RETURNING id, total_score, margin, created_at, updated_at
	`

	err := r.db.Pool.QueryRow(
		ctx, query,
		game.GameID, game.Season, game.Week, game.HomeTeamID, game.AwayTeamID,
		game.HomeTeamCode, game.AwayTeamCode, game.GameDate, game.StadiumID, game.Status,
		game.Period, game.TimeRemaining, game.HomeScore, game.AwayScore,
		game.HomeScoreQuarter1, game.HomeScoreQuarter2, game.HomeScoreQuarter3, game.HomeScoreQuarter4, game.HomeScoreOvertime,
		game.AwayScoreQuarter1, game.AwayScoreQuarter2, game.AwayScoreQuarter3, game.AwayScoreQuarter4, game.AwayScoreOvertime,
	).Scan(&game.ID, &game.TotalScore, &game.Margin, &game.CreatedAt, &game.UpdatedAt)

	if err != nil {
		return fmt.Errorf("failed to upsert game: %w", err)
	}

	return nil
}

// GetByID retrieves a game by its database ID
func (r *GameRepository) GetByID(ctx context.Context, id int) (*models.Game, error) {
	query := `
		SELECT id, game_id, season, week, home_team_id, away_team_id,
		       home_team_code, away_team_code, game_date, stadium_id, status,
		       period, time_remaining, home_score, away_score,
		       home_score_quarter_1, home_score_quarter_2, home_score_quarter_3, home_score_quarter_4, home_score_overtime,
		       away_score_quarter_1, away_score_quarter_2, away_score_quarter_3, away_score_quarter_4, away_score_overtime,
		       total_score, margin, created_at, updated_at
		FROM games
		WHERE id = $1
	`

	var game models.Game
	err := r.db.Pool.QueryRow(ctx, query, id).Scan(
		&game.ID, &game.GameID, &game.Season, &game.Week, &game.HomeTeamID, &game.AwayTeamID,
		&game.HomeTeamCode, &game.AwayTeamCode, &game.GameDate, &game.StadiumID, &game.Status,
		&game.Period, &game.TimeRemaining, &game.HomeScore, &game.AwayScore,
		&game.HomeScoreQuarter1, &game.HomeScoreQuarter2, &game.HomeScoreQuarter3, &game.HomeScoreQuarter4, &game.HomeScoreOvertime,
		&game.AwayScoreQuarter1, &game.AwayScoreQuarter2, &game.AwayScoreQuarter3, &game.AwayScoreQuarter4, &game.AwayScoreOvertime,
		&game.TotalScore, &game.Margin, &game.CreatedAt, &game.UpdatedAt,
	)

	if err == pgx.ErrNoRows {
		return nil, fmt.Errorf("game not found: id=%d", id)
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get game: %w", err)
	}

	return &game, nil
}

// GetByGameID retrieves a game by its SportsDataIO GameID
func (r *GameRepository) GetByGameID(ctx context.Context, gameID int) (*models.Game, error) {
	query := `
		SELECT id, game_id, season, week, home_team_id, away_team_id,
		       home_team_code, away_team_code, game_date, stadium_id, status,
		       period, time_remaining, home_score, away_score,
		       home_score_quarter_1, home_score_quarter_2, home_score_quarter_3, home_score_quarter_4, home_score_overtime,
		       away_score_quarter_1, away_score_quarter_2, away_score_quarter_3, away_score_quarter_4, away_score_overtime,
		       total_score, margin, created_at, updated_at
		FROM games
		WHERE game_id = $1
	`

	var game models.Game
	err := r.db.Pool.QueryRow(ctx, query, gameID).Scan(
		&game.ID, &game.GameID, &game.Season, &game.Week, &game.HomeTeamID, &game.AwayTeamID,
		&game.HomeTeamCode, &game.AwayTeamCode, &game.GameDate, &game.StadiumID, &game.Status,
		&game.Period, &game.TimeRemaining, &game.HomeScore, &game.AwayScore,
		&game.HomeScoreQuarter1, &game.HomeScoreQuarter2, &game.HomeScoreQuarter3, &game.HomeScoreQuarter4, &game.HomeScoreOvertime,
		&game.AwayScoreQuarter1, &game.AwayScoreQuarter2, &game.AwayScoreQuarter3, &game.AwayScoreQuarter4, &game.AwayScoreOvertime,
		&game.TotalScore, &game.Margin, &game.CreatedAt, &game.UpdatedAt,
	)

	if err == pgx.ErrNoRows {
		return nil, fmt.Errorf("game not found: game_id=%d", gameID)
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get game: %w", err)
	}

	return &game, nil
}

// GetActiveGames retrieves all games currently in progress
// This is critical for the scheduler to know which games to poll
func (r *GameRepository) GetActiveGames(ctx context.Context) ([]*models.Game, error) {
	query := `
		SELECT id, game_id, season, week, home_team_id, away_team_id,
		       home_team_code, away_team_code, game_date, stadium_id, status,
		       period, time_remaining, home_score, away_score,
		       home_score_quarter_1, home_score_quarter_2, home_score_quarter_3, home_score_quarter_4, home_score_overtime,
		       away_score_quarter_1, away_score_quarter_2, away_score_quarter_3, away_score_quarter_4, away_score_overtime,
		       total_score, margin, created_at, updated_at
		FROM games
		WHERE status = 'InProgress'
		ORDER BY game_date
	`

	rows, err := r.db.Pool.Query(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("failed to get active games: %w", err)
	}
	defer rows.Close()

	var games []*models.Game
	for rows.Next() {
		var game models.Game
		err := rows.Scan(
			&game.ID, &game.GameID, &game.Season, &game.Week, &game.HomeTeamID, &game.AwayTeamID,
			&game.HomeTeamCode, &game.AwayTeamCode, &game.GameDate, &game.StadiumID, &game.Status,
			&game.Period, &game.TimeRemaining, &game.HomeScore, &game.AwayScore,
			&game.HomeScoreQuarter1, &game.HomeScoreQuarter2, &game.HomeScoreQuarter3, &game.HomeScoreQuarter4, &game.HomeScoreOvertime,
			&game.AwayScoreQuarter1, &game.AwayScoreQuarter2, &game.AwayScoreQuarter3, &game.AwayScoreQuarter4, &game.AwayScoreOvertime,
			&game.TotalScore, &game.Margin, &game.CreatedAt, &game.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan game: %w", err)
		}
		games = append(games, &game)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating games: %w", err)
	}

	log.Debug().Int("count", len(games)).Msg("Retrieved active games")
	return games, nil
}

// GetByWeek retrieves games for a specific season and week
func (r *GameRepository) GetByWeek(ctx context.Context, season, week int) ([]*models.Game, error) {
	query := `
		SELECT id, game_id, season, week, home_team_id, away_team_id,
		       home_team_code, away_team_code, game_date, stadium_id, status,
		       period, time_remaining, home_score, away_score,
		       home_score_quarter_1, home_score_quarter_2, home_score_quarter_3, home_score_quarter_4, home_score_overtime,
		       away_score_quarter_1, away_score_quarter_2, away_score_quarter_3, away_score_quarter_4, away_score_overtime,
		       total_score, margin, created_at, updated_at
		FROM games
		WHERE season = $1 AND week = $2
		ORDER BY game_date
	`

	rows, err := r.db.Pool.Query(ctx, query, season, week)
	if err != nil {
		return nil, fmt.Errorf("failed to get games by week: %w", err)
	}
	defer rows.Close()

	var games []*models.Game
	for rows.Next() {
		var game models.Game
		err := rows.Scan(
			&game.ID, &game.GameID, &game.Season, &game.Week, &game.HomeTeamID, &game.AwayTeamID,
			&game.HomeTeamCode, &game.AwayTeamCode, &game.GameDate, &game.StadiumID, &game.Status,
			&game.Period, &game.TimeRemaining, &game.HomeScore, &game.AwayScore,
			&game.HomeScoreQuarter1, &game.HomeScoreQuarter2, &game.HomeScoreQuarter3, &game.HomeScoreQuarter4, &game.HomeScoreOvertime,
			&game.AwayScoreQuarter1, &game.AwayScoreQuarter2, &game.AwayScoreQuarter3, &game.AwayScoreQuarter4, &game.AwayScoreOvertime,
			&game.TotalScore, &game.Margin, &game.CreatedAt, &game.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan game: %w", err)
		}
		games = append(games, &game)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating games: %w", err)
	}

	return games, nil
}

// GetByStatus retrieves games by status
func (r *GameRepository) GetByStatus(ctx context.Context, status string) ([]*models.Game, error) {
	query := `
		SELECT id, game_id, season, week, home_team_id, away_team_id,
		       home_team_code, away_team_code, game_date, stadium_id, status,
		       period, time_remaining, home_score, away_score,
		       home_score_quarter_1, home_score_quarter_2, home_score_quarter_3, home_score_quarter_4, home_score_overtime,
		       away_score_quarter_1, away_score_quarter_2, away_score_quarter_3, away_score_quarter_4, away_score_overtime,
		       total_score, margin, created_at, updated_at
		FROM games
		WHERE status = $1
		ORDER BY game_date
	`

	rows, err := r.db.Pool.Query(ctx, query, status)
	if err != nil {
		return nil, fmt.Errorf("failed to get games by status: %w", err)
	}
	defer rows.Close()

	var games []*models.Game
	for rows.Next() {
		var game models.Game
		err := rows.Scan(
			&game.ID, &game.GameID, &game.Season, &game.Week, &game.HomeTeamID, &game.AwayTeamID,
			&game.HomeTeamCode, &game.AwayTeamCode, &game.GameDate, &game.StadiumID, &game.Status,
			&game.Period, &game.TimeRemaining, &game.HomeScore, &game.AwayScore,
			&game.HomeScoreQuarter1, &game.HomeScoreQuarter2, &game.HomeScoreQuarter3, &game.HomeScoreQuarter4, &game.HomeScoreOvertime,
			&game.AwayScoreQuarter1, &game.AwayScoreQuarter2, &game.AwayScoreQuarter3, &game.AwayScoreQuarter4, &game.AwayScoreOvertime,
			&game.TotalScore, &game.Margin, &game.CreatedAt, &game.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan game: %w", err)
		}
		games = append(games, &game)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating games: %w", err)
	}

	return games, nil
}

// UpdateStatus updates only the status of a game (lightweight operation)
func (r *GameRepository) UpdateStatus(ctx context.Context, gameID int, status string) error {
	query := `
		UPDATE games
		SET status = $1, updated_at = NOW()
		WHERE game_id = $2
	`

	result, err := r.db.Pool.Exec(ctx, query, status, gameID)
	if err != nil {
		return fmt.Errorf("failed to update game status: %w", err)
	}

	if result.RowsAffected() == 0 {
		return fmt.Errorf("game not found: game_id=%d", gameID)
	}

	return nil
}

// Count returns the total number of games
func (r *GameRepository) Count(ctx context.Context) (int, error) {
	query := `SELECT COUNT(*) FROM games`

	var count int
	err := r.db.Pool.QueryRow(ctx, query).Scan(&count)
	if err != nil {
		return 0, fmt.Errorf("failed to count games: %w", err)
	}

	return count, nil
}
