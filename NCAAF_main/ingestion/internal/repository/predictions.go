package repository

import (
	"context"
	"database/sql"
	"fmt"

	"ncaaf_v5/ingestion/internal/models"

	"github.com/rs/zerolog/log"
)

// PredictionRepository handles prediction-related database operations
type PredictionRepository struct {
	db *Database
}

// CreatePrediction inserts a new prediction atomically with validation
func (r *PredictionRepository) CreatePrediction(ctx context.Context, pred *models.Prediction) error {
	if pred == nil {
		return fmt.Errorf("prediction cannot be nil")
	}

	// Validate prediction data before insert
	if err := validatePredictionData(pred); err != nil {
		return fmt.Errorf("prediction validation failed: %w", err)
	}

	query := `
		INSERT INTO predictions (
			game_id, model_name, model_version,
			predicted_home_score, predicted_away_score, predicted_total, predicted_margin,
			confidence_score,
			consensus_spread, consensus_total, edge_spread, edge_total,
			recommend_bet, recommended_bet_type, recommended_side, recommended_units,
			rationale,
			predicted_at, created_at
		) VALUES (
			$1, $2, $3,
			$4, $5, $6, $7,
			$8,
			$9, $10, $11, $12,
			$13, $14, $15, $16,
			$17,
			$18, $19
		)
		RETURNING id, created_at
	`

	err := r.db.Pool.QueryRow(ctx, query,
		pred.GameID, pred.ModelName, pred.ModelVersion,
		pred.PredictedHomeScore, pred.PredictedAwayScore, pred.PredictedTotal, pred.PredictedMargin,
		pred.ConfidenceScore,
		pred.ConsensusSpread, pred.ConsensusTotal, pred.EdgeSpread, pred.EdgeTotal,
		pred.RecommendBet, pred.RecommendedBetType, pred.RecommendedSide, pred.RecommendedUnits,
		pred.Rationale,
		pred.PredictedAt, pred.CreatedAt,
	).Scan(&pred.ID, &pred.CreatedAt)

	if err != nil {
		log.Error().Err(err).Int("game_id", pred.GameID).Msg("Failed to insert prediction")
		return fmt.Errorf("failed to create prediction: %w", err)
	}

	log.Info().Int("id", pred.ID).Int("game_id", pred.GameID).Msg("Prediction created successfully")
	return nil
}

// GetPredictionByGameID retrieves the most recent prediction for a game
func (r *PredictionRepository) GetPredictionByGameID(ctx context.Context, gameID int) (*models.Prediction, error) {
	query := `
		SELECT id, game_id, model_name, model_version,
			   predicted_home_score, predicted_away_score, predicted_total, predicted_margin,
			   confidence_score,
			   consensus_spread, consensus_total, edge_spread, edge_total,
			   recommend_bet, recommended_bet_type, recommended_side, recommended_units,
			   rationale,
			   predicted_at, created_at
		FROM predictions
		WHERE game_id = $1
		ORDER BY predicted_at DESC
		LIMIT 1
	`

	pred := &models.Prediction{}
	err := r.db.Pool.QueryRow(ctx, query, gameID).Scan(
		&pred.ID, &pred.GameID, &pred.ModelName, &pred.ModelVersion,
		&pred.PredictedHomeScore, &pred.PredictedAwayScore, &pred.PredictedTotal, &pred.PredictedMargin,
		&pred.ConfidenceScore,
		&pred.ConsensusSpread, &pred.ConsensusTotal, &pred.EdgeSpread, &pred.EdgeTotal,
		&pred.RecommendBet, &pred.RecommendedBetType, &pred.RecommendedSide, &pred.RecommendedUnits,
		&pred.Rationale,
		&pred.PredictedAt, &pred.CreatedAt,
	)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get prediction: %w", err)
	}

	return pred, nil
}

// DeletePredictionByGameID deletes a prediction for a game (for retry/correction)
func (r *PredictionRepository) DeletePredictionByGameID(ctx context.Context, gameID int) error {
	query := `DELETE FROM predictions WHERE game_id = $1`

	result, err := r.db.Pool.Exec(ctx, query, gameID)
	if err != nil {
		return fmt.Errorf("failed to delete prediction: %w", err)
	}

	log.Warn().Int64("rows_affected", result.RowsAffected()).Int("game_id", gameID).Msg("Prediction deleted")
	return nil
}

// validatePredictionData ensures prediction data is valid before insertion
func validatePredictionData(pred *models.Prediction) error {
	if pred.GameID <= 0 {
		return fmt.Errorf("game_id must be positive")
	}
	if pred.ModelName == "" {
		return fmt.Errorf("model_name is required")
	}
	if !pred.PredictedHomeScore.Valid || pred.PredictedHomeScore.Float64 < 0 {
		return fmt.Errorf("predicted_home_score must be non-negative")
	}
	if !pred.PredictedAwayScore.Valid || pred.PredictedAwayScore.Float64 < 0 {
		return fmt.Errorf("predicted_away_score must be non-negative")
	}
	if !pred.ConfidenceScore.Valid || pred.ConfidenceScore.Float64 < 0 || pred.ConfidenceScore.Float64 > 1.0 {
		return fmt.Errorf("confidence_score must be between 0 and 1")
	}
	if pred.PredictedAt.IsZero() {
		return fmt.Errorf("predicted_at is required")
	}
	return nil
}
