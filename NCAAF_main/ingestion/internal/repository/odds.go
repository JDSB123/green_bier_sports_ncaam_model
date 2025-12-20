package repository

import (
	"context"
	"fmt"

	"ncaaf_v5/ingestion/internal/models"

	"github.com/jackc/pgx/v5"
	"github.com/rs/zerolog/log"
)

// OddsRepository handles odds and line movement database operations
type OddsRepository struct {
	db *Database
}

// CreateOdds inserts new odds
func (r *OddsRepository) CreateOdds(ctx context.Context, odds *models.Odds) error {
	query := `
		INSERT INTO odds (
			game_id, sportsbook_id, sportsbook_name, market_type, period,
			home_spread, away_spread, over_under, home_moneyline, away_moneyline,
			home_team_total, away_team_total,
			home_spread_juice, away_spread_juice, over_juice, under_juice,
			fetched_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
		RETURNING id, created_at, updated_at
	`

	err := r.db.Pool.QueryRow(
		ctx, query,
		odds.GameID, odds.SportsbookID, odds.SportsbookName, odds.MarketType, odds.Period,
		odds.HomeSpread, odds.AwaySpread, odds.OverUnder, odds.HomeMoneyline, odds.AwayMoneyline,
		odds.HomeTeamTotal, odds.AwayTeamTotal,
		odds.HomeSpreadJuice, odds.AwaySpreadJuice, odds.OverJuice, odds.UnderJuice,
		odds.FetchedAt,
	).Scan(&odds.ID, &odds.CreatedAt, &odds.UpdatedAt)

	if err != nil {
		return fmt.Errorf("failed to create odds: %w", err)
	}

	return nil
}

// GetLatestOdds retrieves the most recent odds for a game from a specific sportsbook
func (r *OddsRepository) GetLatestOdds(ctx context.Context, gameID int, sportsbookID, marketType, period string) (*models.Odds, error) {
	query := `
		SELECT id, game_id, sportsbook_id, sportsbook_name, market_type, period,
		       home_spread, away_spread, over_under, home_moneyline, away_moneyline,
		       home_team_total, away_team_total,
		       home_spread_juice, away_spread_juice, over_juice, under_juice,
		       fetched_at, created_at, updated_at
		FROM odds
		WHERE game_id = $1 AND sportsbook_id = $2 AND market_type = $3 AND period = $4
		ORDER BY fetched_at DESC
		LIMIT 1
	`

	var odds models.Odds
	err := r.db.Pool.QueryRow(ctx, query, gameID, sportsbookID, marketType, period).Scan(
		&odds.ID, &odds.GameID, &odds.SportsbookID, &odds.SportsbookName, &odds.MarketType, &odds.Period,
		&odds.HomeSpread, &odds.AwaySpread, &odds.OverUnder, &odds.HomeMoneyline, &odds.AwayMoneyline,
		&odds.HomeTeamTotal, &odds.AwayTeamTotal,
		&odds.HomeSpreadJuice, &odds.AwaySpreadJuice, &odds.OverJuice, &odds.UnderJuice,
		&odds.FetchedAt, &odds.CreatedAt, &odds.UpdatedAt,
	)

	if err == pgx.ErrNoRows {
		return nil, nil // No odds found is not an error - game may not have odds yet
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get latest odds: %w", err)
	}

	return &odds, nil
}

// GetAllOddsForGame retrieves all odds for a game (all sportsbooks)
func (r *OddsRepository) GetAllOddsForGame(ctx context.Context, gameID int) ([]*models.Odds, error) {
	query := `
		SELECT DISTINCT ON (sportsbook_id, market_type, period)
		       id, game_id, sportsbook_id, sportsbook_name, market_type, period,
		       home_spread, away_spread, over_under, home_moneyline, away_moneyline,
		       home_team_total, away_team_total,
		       home_spread_juice, away_spread_juice, over_juice, under_juice,
		       fetched_at, created_at, updated_at
		FROM odds
		WHERE game_id = $1
		ORDER BY sportsbook_id, market_type, period, fetched_at DESC
	`

	rows, err := r.db.Pool.Query(ctx, query, gameID)
	if err != nil {
		return nil, fmt.Errorf("failed to get odds for game: %w", err)
	}
	defer rows.Close()

	var oddsList []*models.Odds
	for rows.Next() {
		var odds models.Odds
		err := rows.Scan(
			&odds.ID, &odds.GameID, &odds.SportsbookID, &odds.SportsbookName, &odds.MarketType, &odds.Period,
			&odds.HomeSpread, &odds.AwaySpread, &odds.OverUnder, &odds.HomeMoneyline, &odds.AwayMoneyline,
			&odds.HomeTeamTotal, &odds.AwayTeamTotal,
			&odds.HomeSpreadJuice, &odds.AwaySpreadJuice, &odds.OverJuice, &odds.UnderJuice,
			&odds.FetchedAt, &odds.CreatedAt, &odds.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan odds: %w", err)
		}
		oddsList = append(oddsList, &odds)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating odds: %w", err)
	}

	return oddsList, nil
}

// GetConsensusSpread calculates the consensus spread from multiple sharp sportsbooks
func (r *OddsRepository) GetConsensusSpread(ctx context.Context, gameID int, sportsbookIDs []string) (float64, error) {
	query := `
		WITH latest_odds AS (
			SELECT DISTINCT ON (sportsbook_id)
			       home_spread
			FROM odds
			WHERE game_id = $1
			  AND sportsbook_id = ANY($2)
			  AND market_type = 'Game Line'
			  AND period = 'FG'
			  AND home_spread IS NOT NULL
			ORDER BY sportsbook_id, fetched_at DESC
		)
		SELECT AVG(home_spread) as consensus_spread
		FROM latest_odds
	`

	var consensusSpread float64
	err := r.db.Pool.QueryRow(ctx, query, gameID, sportsbookIDs).Scan(&consensusSpread)
	if err == pgx.ErrNoRows {
		return 0, fmt.Errorf("no odds found for consensus calculation")
	}
	if err != nil {
		return 0, fmt.Errorf("failed to calculate consensus spread: %w", err)
	}

	return consensusSpread, nil
}

// GetConsensusTotal calculates the consensus total from multiple sharp sportsbooks
func (r *OddsRepository) GetConsensusTotal(ctx context.Context, gameID int, sportsbookIDs []string) (float64, error) {
	query := `
		WITH latest_odds AS (
			SELECT DISTINCT ON (sportsbook_id)
			       over_under
			FROM odds
			WHERE game_id = $1
			  AND sportsbook_id = ANY($2)
			  AND market_type = 'Total'
			  AND period = 'FG'
			  AND over_under IS NOT NULL
			ORDER BY sportsbook_id, fetched_at DESC
		)
		SELECT AVG(over_under) as consensus_total
		FROM latest_odds
	`

	var consensusTotal float64
	err := r.db.Pool.QueryRow(ctx, query, gameID, sportsbookIDs).Scan(&consensusTotal)
	if err == pgx.ErrNoRows {
		return 0, fmt.Errorf("no odds found for consensus calculation")
	}
	if err != nil {
		return 0, fmt.Errorf("failed to calculate consensus total: %w", err)
	}

	return consensusTotal, nil
}

// CreateLineMovement inserts a line movement record
func (r *OddsRepository) CreateLineMovement(ctx context.Context, movement *models.LineMovement) error {
	query := `
		INSERT INTO line_movement (
			game_id, sportsbook_id, sportsbook_name, market_type, period,
			prev_home_spread, prev_away_spread, prev_over_under, prev_home_moneyline, prev_away_moneyline,
			new_home_spread, new_away_spread, new_over_under, new_home_moneyline, new_away_moneyline,
			movement_timestamp, movement_direction, movement_magnitude
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
		RETURNING id, created_at
	`

	err := r.db.Pool.QueryRow(
		ctx, query,
		movement.GameID, movement.SportsbookID, movement.SportsbookName, movement.MarketType, movement.Period,
		movement.PrevHomeSpread, movement.PrevAwaySpread, movement.PrevOverUnder, movement.PrevHomeMoneyline, movement.PrevAwayMoneyline,
		movement.NewHomeSpread, movement.NewAwaySpread, movement.NewOverUnder, movement.NewHomeMoneyline, movement.NewAwayMoneyline,
		movement.MovementTimestamp, movement.MovementDirection, movement.MovementMagnitude,
	).Scan(&movement.ID, &movement.CreatedAt)

	if err != nil {
		return fmt.Errorf("failed to create line movement: %w", err)
	}

	log.Debug().
		Int("game_id", movement.GameID).
		Str("sportsbook", movement.SportsbookID).
		Str("direction", movement.MovementDirection.String).
		Msg("Line movement recorded")

	return nil
}

// GetLineMovementHistory retrieves line movement history for a game
func (r *OddsRepository) GetLineMovementHistory(ctx context.Context, gameID int, sportsbookID, marketType string) ([]*models.LineMovement, error) {
	query := `
		SELECT id, game_id, sportsbook_id, sportsbook_name, market_type, period,
		       prev_home_spread, prev_away_spread, prev_over_under, prev_home_moneyline, prev_away_moneyline,
		       new_home_spread, new_away_spread, new_over_under, new_home_moneyline, new_away_moneyline,
		       movement_timestamp, movement_direction, movement_magnitude, created_at
		FROM line_movement
		WHERE game_id = $1 AND sportsbook_id = $2 AND market_type = $3
		ORDER BY movement_timestamp ASC
	`

	rows, err := r.db.Pool.Query(ctx, query, gameID, sportsbookID, marketType)
	if err != nil {
		return nil, fmt.Errorf("failed to get line movement history: %w", err)
	}
	defer rows.Close()

	var movements []*models.LineMovement
	for rows.Next() {
		var movement models.LineMovement
		err := rows.Scan(
			&movement.ID, &movement.GameID, &movement.SportsbookID, &movement.SportsbookName, &movement.MarketType, &movement.Period,
			&movement.PrevHomeSpread, &movement.PrevAwaySpread, &movement.PrevOverUnder, &movement.PrevHomeMoneyline, &movement.PrevAwayMoneyline,
			&movement.NewHomeSpread, &movement.NewAwaySpread, &movement.NewOverUnder, &movement.NewHomeMoneyline, &movement.NewAwayMoneyline,
			&movement.MovementTimestamp, &movement.MovementDirection, &movement.MovementMagnitude, &movement.CreatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan line movement: %w", err)
		}
		movements = append(movements, &movement)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating line movements: %w", err)
	}

	return movements, nil
}

// TrackAndSaveOdds checks for line movement and saves new odds
// This is the main method called by the scheduler
func (r *OddsRepository) TrackAndSaveOdds(ctx context.Context, newOdds *models.Odds) error {
	// Get previous odds
	prevOdds, err := r.GetLatestOdds(
		ctx,
		newOdds.GameID,
		newOdds.SportsbookID,
		newOdds.MarketType,
		newOdds.Period,
	)
	if err != nil {
		return fmt.Errorf("failed to get previous odds: %w", err)
	}

	// Save new odds
	if err := r.CreateOdds(ctx, newOdds); err != nil {
		return fmt.Errorf("failed to save odds: %w", err)
	}

	// Check for line movement
	if prevOdds != nil {
		movement := models.DetectLineMovement(prevOdds, newOdds)
		if movement != nil {
			if err := r.CreateLineMovement(ctx, movement); err != nil {
				// Log error but don't fail the whole operation
				log.Error().
					Err(err).
					Int("game_id", newOdds.GameID).
					Str("sportsbook", newOdds.SportsbookID).
					Msg("Failed to record line movement")
			}
		}
	}

	return nil
}
