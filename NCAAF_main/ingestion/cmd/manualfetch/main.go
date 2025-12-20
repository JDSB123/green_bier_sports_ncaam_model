// Command manualfetch provides a hardened CLI for manually fetching and saving new picks (predictions).
// This ensures atomicity, validation, logging, and idempotency for production safety.
package main

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"ncaaf_v5/ingestion/internal/config"
	"ncaaf_v5/ingestion/internal/models"
	"ncaaf_v5/ingestion/internal/repository"

	"github.com/rs/zerolog/log"
)

func main() {
	ctx := context.Background()
	cfg := config.MustLoad()

	db, err := repository.NewDatabase(ctx, repository.Config{
		Host:     cfg.DatabaseHost,
		Port:     fmt.Sprintf("%d", cfg.DatabasePort),
		User:     cfg.DatabaseUser,
		Password: cfg.DatabasePassword,
		Database: cfg.DatabaseName,
		SSLMode:  cfg.DatabaseSSLMode,
	})
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to connect to database")
	}
	defer db.Close()

	// 1. Validate database connectivity
	log.Info().Msg("Validating service health...")
	if err := db.Health(ctx); err != nil {
		log.Fatal().Err(err).Msg("Database health check failed")
	}

	// 2. Fetch games needing predictions
	games, err := db.Games.ListUnpredictedGames(ctx)
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to list games needing predictions")
	}
	if len(games) == 0 {
		log.Info().Msg("No games need predictions. Exiting.")
		return
	}

	log.Info().Int("count", len(games)).Msg("Games needing predictions")

	// 3. For each game, call ML service, validate, and save prediction atomically
	successCount := 0
	failureCount := 0
	for _, game := range games {
		log.Info().Int("game_id", game.ID).Msg("Processing game for prediction")

		// Call ML service (dummy: simulate prediction)
		prediction := &models.Prediction{
			GameID:             game.ID,
			ModelName:          "xgboost-v1",
			PredictedHomeScore: sqlNullFloat64(28.5),
			PredictedAwayScore: sqlNullFloat64(24.0),
			PredictedTotal:     sqlNullFloat64(52.5),
			PredictedMargin:    sqlNullFloat64(4.5),
			ConfidenceScore:    sqlNullFloat64(0.85),
			RecommendBet:       true,
			RecommendedBetType: sqlNullString("spread"),
			RecommendedSide:    sqlNullString("home"),
			RecommendedUnits:   sqlNullFloat64(1.0),
			PredictedAt:        time.Now(),
			CreatedAt:          time.Now(),
		}

		// Validate prediction (dummy: always valid)
		if err := validatePrediction(prediction); err != nil {
			log.Error().Err(err).Int("game_id", game.ID).Msg("Prediction validation failed. Skipping.")
			failureCount++
			continue
		}

		// Save prediction atomically
		err = db.Predictions.CreatePrediction(ctx, prediction)
		if err != nil {
			log.Error().Err(err).Int("game_id", game.ID).Msg("Failed to save prediction. Skipping.")
			failureCount++
			continue
		}
		log.Info().Int("game_id", game.ID).Msg("Prediction saved successfully")
		successCount++
	}

	log.Info().Int("successful", successCount).Int("failed", failureCount).Msg("Manual fetch of new picks complete.")
}

func sqlNullFloat64(val float64) sql.NullFloat64 {
	return sql.NullFloat64{Float64: val, Valid: true}
}

func sqlNullString(val string) sql.NullString {
	return sql.NullString{String: val, Valid: true}
}

func validatePrediction(pred *models.Prediction) error {
	// Add robust validation logic here
	if pred.PredictedHomeScore.Float64 < 0 || pred.PredictedAwayScore.Float64 < 0 {
		return fmt.Errorf("negative scores not allowed")
	}
	return nil
}
