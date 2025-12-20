package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"ncaaf_v5/ingestion/internal/cache"
	"ncaaf_v5/ingestion/internal/client"
	"ncaaf_v5/ingestion/internal/config"
	"ncaaf_v5/ingestion/internal/metrics"
	"ncaaf_v5/ingestion/internal/models"
	"ncaaf_v5/ingestion/internal/repository"
	"ncaaf_v5/ingestion/internal/scheduler"

	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
)

func main() {
	// Setup logger
	setupLogger()

	log.Info().Msg("Starting NCAAF v5.0 Data Ingestion Worker")

	// Load configuration
	cfg := config.MustLoad()
	log.Info().
		Str("env", cfg.AppEnv).
		Str("log_level", cfg.LogLevel).
		Msg("Configuration loaded")

	// Create context that listens for cancellation
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Setup graceful shutdown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	go func() {
		<-sigChan
		log.Info().Msg("Received shutdown signal, gracefully shutting down...")
		cancel()
	}()

	// Initialize SportsDataIO client
	sdioClient := client.NewClient(
		cfg.SportsDataBaseURL,
		cfg.SportsDataAPIKey,
		cfg.SportsDataTimeout,
	)
	log.Info().Msg("SportsDataIO client initialized")

	// Initialize database connection
	dbConfig := repository.Config{
		Host:     cfg.DatabaseHost,
		Port:     strconv.Itoa(cfg.DatabasePort),
		User:     cfg.DatabaseUser,
		Password: cfg.DatabasePassword,
		Database: cfg.DatabaseName,
		SSLMode:  cfg.DatabaseSSLMode,
	}

	db, err := repository.NewDatabase(ctx, dbConfig)
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to connect to database")
	}
	defer db.Close()
	log.Info().Msg("Database connection established")

	// Initialize Redis client
	redisCache, err := cache.NewRedisCache(cache.Config{
		Host:     cfg.RedisHost,
		Port:     strconv.Itoa(cfg.RedisPort),
		Password: cfg.RedisPassword,
		DB:       cfg.RedisDB,
	})
	if err != nil {
		log.Warn().Err(err).Msg("Failed to connect to Redis - continuing without cache")
	} else {
		defer redisCache.Close()
		log.Info().Msg("Redis cache connected")
	}

	// Start metrics HTTP server
	metricsPort := os.Getenv("METRICS_PORT")
	if metricsPort == "" {
		metricsPort = "9090"
	}
	go startMetricsServer(metricsPort)

	// Update system uptime metric
	startTime := time.Now()
	go func() {
		ticker := time.NewTicker(10 * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				metrics.SystemUptime.Set(time.Since(startTime).Seconds())
			case <-ctx.Done():
				return
			}
		}
	}()

	// Create and start scheduler
	sched := scheduler.NewScheduler(cfg, sdioClient, db)

	if cfg.EnableScheduler {
		log.Info().Msg("Starting scheduler...")
		if err := sched.Start(ctx); err != nil {
			log.Fatal().Err(err).Msg("Failed to start scheduler")
		}
	}

	// Run initial sync if enabled
	if cfg.InitialSyncEnabled {
		log.Info().Msg("Running initial data sync...")
		if err := runInitialSync(ctx, sdioClient, db); err != nil {
			log.Error().Err(err).Msg("Initial sync failed, continuing anyway...")
		} else {
			log.Info().Msg("Initial sync completed successfully")
		}

		// Historical backfill for 2024 season (Nov-Dec backtesting data)
		log.Info().Msg("Running historical backfill for 2024 season...")
		if err := runHistoricalBackfill(ctx, sdioClient, db); err != nil {
			log.Error().Err(err).Msg("Historical backfill failed, continuing anyway...")
		} else {
			log.Info().Msg("Historical backfill completed successfully")
		}
	}

	// Keep running until context is cancelled
	<-ctx.Done()

	// Graceful shutdown
	log.Info().Msg("Shutting down scheduler...")
	sched.Stop()

	log.Info().Msg("Worker shutdown complete")
}

// setupLogger configures the zerolog logger
func setupLogger() {
	// Pretty console logging in development
	if os.Getenv("APP_ENV") == "development" {
		log.Logger = log.Output(zerolog.ConsoleWriter{
			Out:        os.Stdout,
			TimeFormat: time.RFC3339,
		})
	}

	// Set log level
	level := zerolog.InfoLevel
	if lvl := os.Getenv("LOG_LEVEL"); lvl != "" {
		parsedLevel, err := zerolog.ParseLevel(lvl)
		if err == nil {
			level = parsedLevel
		}
	}
	zerolog.SetGlobalLevel(level)

	log.Info().
		Str("level", level.String()).
		Msg("Logger initialized")
}

// runInitialSync performs the initial data synchronization
// Following SportsDataIO best practice: sync static data once on startup
func runInitialSync(ctx context.Context, client *client.Client, db *repository.Database) error {
	log.Info().Msg("Fetching current season and week...")
	season, err := client.FetchCurrentSeason(ctx)
	if err != nil {
		return err
	}
	week, err := client.FetchCurrentWeek(ctx)
	if err != nil {
		return err
	}
	log.Info().
		Int("season", season).
		Int("week", week).
		Msg("Current season and week fetched")

	// Fetch and save teams
	log.Info().Msg("Fetching teams...")
	teamsData, err := client.FetchTeams(ctx)
	if err != nil {
		return err
	}
	log.Info().Int("count", len(teamsData)).Msg("Teams fetched")

	// Save teams to database
	savedTeams := 0
	for _, teamData := range teamsData {
		// Marshal back to JSON then unmarshal to TeamInput struct
		jsonData, err := json.Marshal(teamData)
		if err != nil {
			log.Warn().Err(err).Msg("Failed to marshal team data")
			continue
		}

		var teamInput models.TeamInput
		if err := json.Unmarshal(jsonData, &teamInput); err != nil {
			log.Warn().Err(err).Msg("Failed to unmarshal team data")
			continue
		}

		// Convert to Team model and save
		team := teamInput.ToTeam()
		if err := db.Teams.Upsert(ctx, team); err != nil {
			log.Error().Err(err).Int("team_id", teamInput.TeamID).Msg("Failed to save team")
			continue
		}

		savedTeams++
		log.Debug().
			Int("team_id", team.TeamID).
			Str("school", team.SchoolName).
			Str("code", team.TeamCode).
			Msg("Team saved successfully")
	}
	log.Info().Int("count", savedTeams).Msg("Teams saved to database")

	// Fetch and save stadiums
	log.Info().Msg("Fetching stadiums...")
	stadiumsData, err := client.FetchStadiums(ctx)
	if err != nil {
		return err
	}
	log.Info().Int("count", len(stadiumsData)).Msg("Stadiums fetched")

	// Save stadiums to database
	savedStadiums := 0
	for _, stadiumData := range stadiumsData {
		// Marshal back to JSON then unmarshal to StadiumInput struct
		jsonData, err := json.Marshal(stadiumData)
		if err != nil {
			log.Warn().Err(err).Msg("Failed to marshal stadium data")
			continue
		}

		var stadiumInput models.StadiumInput
		if err := json.Unmarshal(jsonData, &stadiumInput); err != nil {
			log.Warn().Err(err).Msg("Failed to unmarshal stadium data")
			continue
		}

		// Convert to Stadium model and save directly
		stadium := stadiumInput.ToStadium()

		// Direct SQL insert since StadiumRepository doesn't exist yet
		query := `
			INSERT INTO stadiums (stadium_id, name, city, state, country, capacity, surface)
			VALUES ($1, $2, $3, $4, $5, $6, $7)
			ON CONFLICT (stadium_id) DO UPDATE SET
				name = EXCLUDED.name,
				city = EXCLUDED.city,
				state = EXCLUDED.state,
				country = EXCLUDED.country,
				capacity = EXCLUDED.capacity,
				surface = EXCLUDED.surface,
				updated_at = NOW()
		`

		_, err = db.Pool.Exec(ctx, query,
			stadium.StadiumID, stadium.Name, stadium.City, stadium.State,
			stadium.Country, stadium.Capacity, stadium.Surface,
		)
		if err != nil {
			log.Error().Err(err).Int("stadium_id", stadiumInput.StadiumID).Msg("Failed to save stadium")
			continue
		}

		savedStadiums++
		log.Debug().
			Int("stadium_id", stadium.StadiumID).
			Str("name", stadium.Name).
			Msg("Stadium saved successfully")
	}
	log.Info().Int("count", savedStadiums).Msg("Stadiums saved to database")

	// Fetch games for current season
	log.Info().Int("season", season).Msg("Fetching games for current season...")
	gamesData, err := client.FetchGames(ctx, fmt.Sprintf("%d", season))
	if err != nil {
		return err
	}
	log.Info().Int("count", len(gamesData)).Msg("Games fetched")

	// Save games to database
	savedGames := 0
	for _, gameData := range gamesData {
		// Marshal back to JSON then unmarshal to GameInput struct
		jsonData, err := json.Marshal(gameData)
		if err != nil {
			log.Warn().Err(err).Msg("Failed to marshal game data")
			continue
		}

		var gameInput models.GameInput
		if err := json.Unmarshal(jsonData, &gameInput); err != nil {
			log.Warn().Err(err).Msg("Failed to unmarshal game data")
			continue
		}

		// Look up home and away team database IDs by team code
		homeTeam, err := db.Teams.GetByTeamCode(ctx, gameInput.HomeTeam)
		if err != nil {
			log.Warn().
				Err(err).
				Str("home_team_code", gameInput.HomeTeam).
				Int("game_id", gameInput.GameID).
				Msg("Failed to find home team, skipping game")
			continue
		}

		awayTeam, err := db.Teams.GetByTeamCode(ctx, gameInput.AwayTeam)
		if err != nil {
			log.Warn().
				Err(err).
				Str("away_team_code", gameInput.AwayTeam).
				Int("game_id", gameInput.GameID).
				Msg("Failed to find away team, skipping game")
			continue
		}

		// Convert to Game model and save
		game := gameInput.ToGame(homeTeam.ID, awayTeam.ID)
		if err := db.Games.Upsert(ctx, game); err != nil {
			log.Error().Err(err).Int("game_id", gameInput.GameID).Msg("Failed to save game")
			continue
		}

		savedGames++
		log.Debug().
			Int("game_id", game.GameID).
			Str("home", game.HomeTeamCode).
			Str("away", game.AwayTeamCode).
			Str("status", game.Status).
			Msg("Game saved successfully")
	}
	log.Info().Int("count", savedGames).Msg("Games saved to database")

	log.Info().Msg("Initial sync complete")
	return nil
}

// runHistoricalBackfill fetches historical 2024 season data for backtesting
// Focuses on November-December 2024 (weeks 10-15) with complete scores and odds
func runHistoricalBackfill(ctx context.Context, client *client.Client, db *repository.Database) error {
	const historicalSeason = "2024"

	// STEP 0: Re-fetch 2024 games to get scores for Final games
	log.Info().Msg("Re-fetching 2024 games to update scores...")
	gamesData, err := client.FetchGames(ctx, historicalSeason)
	if err != nil {
		log.Warn().Err(err).Msg("Failed to re-fetch 2024 games")
	} else {
		log.Info().Int("count", len(gamesData)).Msg("2024 games re-fetched")
		updatedScores := 0
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
			if (gameInput.Status != "Final" && gameInput.Status != "F/OT") || gameInput.HomeScore == nil || gameInput.AwayScore == nil {
				continue
			}

			// Get existing game by SportsDataIO GameID
			existingGame, err := db.Games.GetByGameID(ctx, gameInput.GameID)
			if err != nil {
				continue
			}

			// Update with scores
			game := gameInput.ToGame(existingGame.HomeTeamID, existingGame.AwayTeamID)
			if err := db.Games.Upsert(ctx, game); err != nil {
				continue
			}
			updatedScores++
		}
		log.Info().Int("updated", updatedScores).Msg("Games updated with scores")
	}
	historicalWeeks := []int{10, 11, 12, 13, 14, 15} // Nov-Dec 2024

	log.Info().
		Str("season", historicalSeason).
		Ints("weeks", historicalWeeks).
		Msg("Starting historical backfill")

	// 1. Fetch all 2024 season games (for context)
	log.Info().Str("season", historicalSeason).Msg("Fetching 2024 season games...")
	gamesData, err := client.FetchGames(ctx, historicalSeason)
	if err != nil {
		return fmt.Errorf("failed to fetch 2024 games: %w", err)
	}
	log.Info().Int("count", len(gamesData)).Msg("2024 games fetched")

	// Save 2024 games
	savedGames := 0
	for _, gameData := range gamesData {
		jsonData, err := json.Marshal(gameData)
		if err != nil {
			continue
		}

		var gameInput models.GameInput
		if err := json.Unmarshal(jsonData, &gameInput); err != nil {
			continue
		}

		// Look up team IDs
		homeTeam, err := db.Teams.GetByTeamCode(ctx, gameInput.HomeTeam)
		if err != nil {
			continue
		}
		awayTeam, err := db.Teams.GetByTeamCode(ctx, gameInput.AwayTeam)
		if err != nil {
			continue
		}

		// Save game
		game := gameInput.ToGame(homeTeam.ID, awayTeam.ID)
		if err := db.Games.Upsert(ctx, game); err != nil {
			log.Error().Err(err).Int("game_id", gameInput.GameID).Msg("Failed to save 2024 game")
			continue
		}
		savedGames++
	}
	log.Info().Int("count", savedGames).Msg("2024 games saved to database")

	// 2. Fetch box scores for each target week (for quarter-by-quarter scores)
	for _, week := range historicalWeeks {
		log.Info().
			Str("season", historicalSeason).
			Int("week", week).
			Msg("Fetching box scores...")

		boxScores, err := client.FetchBoxScoresByWeek(ctx, historicalSeason, week)
		if err != nil {
			log.Warn().Err(err).Int("week", week).Msg("Failed to fetch box scores")
			continue
		}

		log.Info().
			Int("week", week).
			Int("count", len(boxScores)).
			Msg("Box scores fetched, updating games with quarter scores...")

		// Update games with quarter-by-quarter scores from box scores
		// Box scores API returns nested structure: {Game: {...}, TeamGames: [...]}
		for _, boxScoreRaw := range boxScores {
			// Extract Game object from box score
			gameObj, ok := boxScoreRaw["Game"].(map[string]interface{})
			if !ok {
				log.Debug().Msg("Box score missing Game object, skipping")
				continue
			}

			gameID, ok := gameObj["GameID"].(float64)
			if !ok {
				continue
			}
			gameIDInt := int(gameID)

			// Get existing game from database
			existingGame, err := db.Games.GetByGameID(ctx, gameIDInt)
			if err != nil {
				log.Debug().Err(err).Int("game_id", gameIDInt).Msg("Game not found in database, skipping")
				continue
			}

			// Extract scores from Game object
			var homeScore, awayScore *int
			if hs, ok := gameObj["HomeScore"].(float64); ok {
				hsInt := int(hs)
				homeScore = &hsInt
			}
			if as, ok := gameObj["AwayScore"].(float64); ok {
				asInt := int(as)
				awayScore = &asInt
			}

			// Extract TeamGames array for quarter scores
			teamGames, ok := boxScoreRaw["TeamGames"].([]interface{})
			if ok {
				var homeQ1, homeQ2, homeQ3, homeQ4, homeOT *int
				var awayQ1, awayQ2, awayQ3, awayQ4, awayOT *int

				for _, tg := range teamGames {
					teamGame, ok := tg.(map[string]interface{})
					if !ok {
						continue
					}

					homeOrAway, _ := teamGame["HomeOrAway"].(string)

					// Extract quarter scores
					extractQuarter := func(key string) *int {
						if val, ok := teamGame[key].(float64); ok {
							v := int(val)
							return &v
						}
						return nil
					}

					if homeOrAway == "HOME" {
						homeQ1 = extractQuarter("ScoreQuarter1")
						homeQ2 = extractQuarter("ScoreQuarter2")
						homeQ3 = extractQuarter("ScoreQuarter3")
						homeQ4 = extractQuarter("ScoreQuarter4")
						homeOT = extractQuarter("ScoreQuarterOvertime")
						// If total score not from Game object, use Points
						if homeScore == nil {
							if points, ok := teamGame["Points"].(float64); ok {
								p := int(points)
								homeScore = &p
							}
						}
					} else if homeOrAway == "AWAY" {
						awayQ1 = extractQuarter("ScoreQuarter1")
						awayQ2 = extractQuarter("ScoreQuarter2")
						awayQ3 = extractQuarter("ScoreQuarter3")
						awayQ4 = extractQuarter("ScoreQuarter4")
						awayOT = extractQuarter("ScoreQuarterOvertime")
						// If total score not from Game object, use Points
						if awayScore == nil {
							if points, ok := teamGame["Points"].(float64); ok {
								p := int(points)
								awayScore = &p
							}
						}
					}
				}

				// Build GameInput with extracted scores
				gameInput := &models.GameInput{
					GameID:            gameIDInt,
					Season:            existingGame.Season,
					Week:              existingGame.Week,
					HomeTeamID:        existingGame.HomeTeamID,
					AwayTeamID:        existingGame.AwayTeamID,
					HomeTeam:          existingGame.HomeTeamCode,
					AwayTeam:          existingGame.AwayTeamCode,
					Status:            existingGame.Status,
					HomeScore:         homeScore,
					AwayScore:         awayScore,
					HomeScoreQuarter1: homeQ1,
					HomeScoreQuarter2: homeQ2,
					HomeScoreQuarter3: homeQ3,
					HomeScoreQuarter4: homeQ4,
					HomeScoreOvertime: homeOT,
					AwayScoreQuarter1: awayQ1,
					AwayScoreQuarter2: awayQ2,
					AwayScoreQuarter3: awayQ3,
					AwayScoreQuarter4: awayQ4,
					AwayScoreOvertime: awayOT,
				}

				game := gameInput.ToGame(existingGame.HomeTeamID, existingGame.AwayTeamID)
				if err := db.Games.Upsert(ctx, game); err != nil {
					log.Warn().Err(err).Int("game_id", gameIDInt).Msg("Failed to update game with box score data")
					continue
				}

				log.Debug().
					Int("game_id", gameIDInt).
					Interface("home_score", homeScore).
					Interface("away_score", awayScore).
					Msg("Updated game with box score data")
			} else if homeScore != nil && awayScore != nil {
				// If no TeamGames but we have scores, update just the scores
				gameInput := &models.GameInput{
					GameID:     gameIDInt,
					Season:     existingGame.Season,
					Week:       existingGame.Week,
					HomeTeamID: existingGame.HomeTeamID,
					AwayTeamID: existingGame.AwayTeamID,
					HomeTeam:   existingGame.HomeTeamCode,
					AwayTeam:   existingGame.AwayTeamCode,
					Status:     existingGame.Status,
					HomeScore:  homeScore,
					AwayScore:  awayScore,
				}
				game := gameInput.ToGame(existingGame.HomeTeamID, existingGame.AwayTeamID)
				if err := db.Games.Upsert(ctx, game); err != nil {
					log.Warn().Err(err).Int("game_id", gameIDInt).Msg("Failed to update game scores")
					continue
				}
			}
		}
	}

	// 3. Fetch historical odds for each target week
	savedOdds := 0
	for _, week := range historicalWeeks {
		log.Info().
			Str("season", historicalSeason).
			Int("week", week).
			Msg("Fetching historical odds...")

		// Fetch sharp odds (Pinnacle + Circa)
		sharpOdds, err := client.FetchSharpOdds(ctx, historicalSeason, week)
		if err != nil {
			log.Warn().Err(err).Int("week", week).Msg("Failed to fetch sharp odds")
		} else {
			log.Info().Int("week", week).Int("count", len(sharpOdds)).Msg("Sharp odds games fetched")

			// Save sharp odds - parse nested structure
			for _, gameOddsData := range sharpOdds {
				jsonData, err := json.Marshal(gameOddsData)
				if err != nil {
					continue
				}

				var gameOdds models.GameOddsResponse
				if err := json.Unmarshal(jsonData, &gameOdds); err != nil {
					continue
				}

				// Look up game by GameID from API
				game, err := db.Games.GetByGameID(ctx, gameOdds.GameID)
				if err != nil {
					continue
				}

				// Process all pregame odds for this game
				for _, oddsInput := range gameOdds.PregameOdds {
					odds := oddsInput.ToOdds(game.ID)
					if err := db.Odds.CreateOdds(ctx, odds); err != nil {
						log.Debug().Err(err).Int("game_id", gameOdds.GameID).Str("sportsbook", oddsInput.SportsbookName).Msg("Failed to save odds")
						continue
					}
					savedOdds++
				}
			}
		}

		// Fetch public odds (DraftKings, FanDuel, etc.)
		publicOdds, err := client.FetchPublicOdds(ctx, historicalSeason, week)
		if err != nil {
			log.Warn().Err(err).Int("week", week).Msg("Failed to fetch public odds")
		} else {
			log.Info().Int("week", week).Int("count", len(publicOdds)).Msg("Public odds games fetched")

			// Save public odds - parse nested structure
			for _, gameOddsData := range publicOdds {
				jsonData, err := json.Marshal(gameOddsData)
				if err != nil {
					continue
				}

				var gameOdds models.GameOddsResponse
				if err := json.Unmarshal(jsonData, &gameOdds); err != nil {
					continue
				}

				// Look up game by GameID from API
				game, err := db.Games.GetByGameID(ctx, gameOdds.GameID)
				if err != nil {
					continue
				}

				// Process all pregame odds for this game
				for _, oddsInput := range gameOdds.PregameOdds {
					odds := oddsInput.ToOdds(game.ID)
					if err := db.Odds.CreateOdds(ctx, odds); err != nil {
						log.Debug().Err(err).Int("game_id", gameOdds.GameID).Str("sportsbook", oddsInput.SportsbookName).Msg("Failed to save odds")
						continue
					}
					savedOdds++
				}
			}
		}
	}

	log.Info().Int("count", savedOdds).Msg("Historical odds saved to database")
	log.Info().Msg("Historical backfill complete")
	return nil
}

// startMetricsServer starts the Prometheus metrics HTTP server
func startMetricsServer(port string) {
	http.Handle("/metrics", promhttp.Handler())

	// Health check endpoint
	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"healthy"}`))
	})

	addr := fmt.Sprintf(":%s", port)
	log.Info().Str("port", port).Msg("Starting metrics server")

	if err := http.ListenAndServe(addr, nil); err != nil {
		log.Error().Err(err).Msg("Metrics server failed")
	}
}
