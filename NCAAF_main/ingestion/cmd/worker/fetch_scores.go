package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"

	"ncaaf_v5/ingestion/internal/client"
	"ncaaf_v5/ingestion/internal/config"
	"ncaaf_v5/ingestion/internal/models"
	"ncaaf_v5/ingestion/internal/repository"
)

// fetchAndUpdateScores re-fetches games for 2024 season to get scores
func fetchAndUpdateScores() error {
	ctx := context.Background()

	// Load config
	cfg, err := config.Load()
	if err != nil {
		return fmt.Errorf("failed to load config: %w", err)
	}

	// Initialize database
	db, err := repository.NewDatabase(cfg.Database)
	if err != nil {
		return fmt.Errorf("failed to connect to database: %w", err)
	}
	defer db.Close()

	// Initialize API client
	apiClient := client.NewClient(cfg.SportsDataIO.BaseURL, cfg.SportsDataIO.APIKey, cfg.SportsDataIO.Timeout)

	// Fetch 2024 season games (should include scores for Final games)
	log.Println("Fetching 2024 season games with scores...")
	gamesData, err := apiClient.FetchGames(ctx, "2024")
	if err != nil {
		return fmt.Errorf("failed to fetch games: %w", err)
	}

	log.Printf("Fetched %d games", len(gamesData))

	updated := 0
	for _, gameData := range gamesData {
		jsonData, err := json.Marshal(gameData)
		if err != nil {
			continue
		}

		var gameInput models.GameInput
		if err := json.Unmarshal(jsonData, &gameInput); err != nil {
			continue
		}

		// Only update Final games with scores
		if gameInput.Status != "Final" && gameInput.Status != "F/OT" {
			continue
		}

		if gameInput.HomeScore == nil || gameInput.AwayScore == nil {
			continue
		}

		// Get existing game
		existingGame, err := db.Games.GetByGameID(ctx, gameInput.GameID)
		if err != nil {
			continue
		}

		// Update scores
		game := gameInput.ToGame(existingGame.HomeTeamID, existingGame.AwayTeamID)
		if err := db.Games.Upsert(ctx, game); err != nil {
			log.Printf("Failed to update game %d: %v", gameInput.GameID, err)
			continue
		}

		updated++
		if updated%50 == 0 {
			log.Printf("Updated %d games...", updated)
		}
	}

	log.Printf("Successfully updated %d games with scores", updated)
	return nil
}
