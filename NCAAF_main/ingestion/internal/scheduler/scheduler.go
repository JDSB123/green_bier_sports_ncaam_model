package scheduler

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"ncaaf_v5/ingestion/internal/client"
	"ncaaf_v5/ingestion/internal/config"
	"ncaaf_v5/ingestion/internal/models"
	"ncaaf_v5/ingestion/internal/repository"

	"github.com/robfig/cron/v3"
	"github.com/rs/zerolog/log"
)

// Scheduler manages background tasks for data ingestion
// Implements SportsDataIO best practices:
// - Poll active games every minute
// - Nightly refresh of static data
// - Conditional fetching (only active games)
type Scheduler struct {
	cfg      *config.Config
	client   *client.Client
	db       *repository.Database
	cron     *cron.Cron
	ticker   *time.Ticker
	stopChan chan struct{}
}

// NewScheduler creates a new scheduler instance
func NewScheduler(cfg *config.Config, client *client.Client, db *repository.Database) *Scheduler {
	return &Scheduler{
		cfg:      cfg,
		client:   client,
		db:       db,
		cron:     cron.New(),
		stopChan: make(chan struct{}),
	}
}

// Start starts the scheduler
func (s *Scheduler) Start(ctx context.Context) error {
	log.Info().Msg("Scheduler starting...")

	// Setup nightly refresh cron job
	if _, err := s.cron.AddFunc(s.cfg.NightlyRefreshCron, func() {
		log.Info().Msg("Running nightly refresh...")
		if err := s.refreshStaticData(ctx); err != nil {
			log.Error().Err(err).Msg("Nightly refresh failed")
		}
	}); err != nil {
		return fmt.Errorf("failed to schedule nightly refresh: %w", err)
	}

	// Start cron scheduler
	s.cron.Start()
	log.Info().
		Str("schedule", s.cfg.NightlyRefreshCron).
		Msg("Nightly refresh scheduled")

	// Start active game polling ticker
	// This follows SportsDataIO best practice: poll every minute for in-progress games
	interval := time.Duration(s.cfg.ActiveGamePollInterval) * time.Second
	s.ticker = time.NewTicker(interval)
	log.Info().
		Dur("interval", interval).
		Msg("Active game polling started")

	// Start polling goroutine
	go s.pollActiveGames(ctx)

	return nil
}

// Stop stops the scheduler
func (s *Scheduler) Stop() {
	log.Info().Msg("Stopping scheduler...")

	if s.cron != nil {
		s.cron.Stop()
	}

	if s.ticker != nil {
		s.ticker.Stop()
	}

	close(s.stopChan)
	log.Info().Msg("Scheduler stopped")
}

// pollActiveGames continuously polls for active games
// SportsDataIO Best Practice: Only fetch games that are in progress
func (s *Scheduler) pollActiveGames(ctx context.Context) {
	for {
		select {
		case <-ctx.Done():
			log.Info().Msg("Context cancelled, stopping active game polling")
			return
		case <-s.stopChan:
			log.Info().Msg("Stop signal received, stopping active game polling")
			return
		case <-s.ticker.C:
			if err := s.fetchAndUpdateActiveGames(ctx); err != nil {
				log.Error().Err(err).Msg("Failed to fetch active games")
			}
		}
	}
}

// fetchAndUpdateActiveGames fetches and updates data for currently active games
func (s *Scheduler) fetchAndUpdateActiveGames(ctx context.Context) error {
	start := time.Now()

	// Get current season and week
	season, err := s.client.FetchCurrentSeason(ctx)
	if err != nil {
		return fmt.Errorf("failed to fetch current season: %w", err)
	}

	week, err := s.client.FetchCurrentWeek(ctx)
	if err != nil {
		return fmt.Errorf("failed to fetch current week: %w", err)
	}

	log.Debug().
		Int("season", season).
		Int("week", week).
		Msg("Checking for active games")

	// Query database for active games
	// Following SportsDataIO best practice: only fetch games that are in progress
	activeGames, err := s.db.Games.GetActiveGames(ctx)
	if err != nil {
		return fmt.Errorf("failed to get active games: %w", err)
	}

	if len(activeGames) == 0 {
		log.Debug().Msg("No active games found")
		log.Info().
			Dur("duration", time.Since(start)).
			Msg("Active game check complete")
		return nil
	}

	log.Info().Int("count", len(activeGames)).Msg("Found active games")

	// Fetch and update data for active games in parallel
	var wg sync.WaitGroup
	for _, game := range activeGames {
		wg.Add(1)
		go func(g *models.Game) {
			defer wg.Done()
			if err := s.updateGameData(ctx, g.GameID); err != nil {
				log.Error().Err(err).Int("game_id", g.GameID).Msg("Failed to update game")
			}
		}(game)
	}

	wg.Wait()

	log.Info().
		Int("active_games", len(activeGames)).
		Dur("duration", time.Since(start)).
		Msg("Active game polling complete")

	return nil
}

// refreshStaticData refreshes static data (teams, stadiums)
// SportsDataIO Best Practice: Refresh static data nightly during off-hours
func (s *Scheduler) refreshStaticData(ctx context.Context) error {
	log.Info().Msg("Refreshing static data...")

	// Fetch and upsert teams
	teamsData, err := s.client.FetchTeams(ctx)
	if err != nil {
		return fmt.Errorf("failed to fetch teams: %w", err)
	}
	log.Info().Int("count", len(teamsData)).Msg("Teams fetched")

	// Convert API response to models and upsert
	savedTeams := 0
	for _, teamData := range teamsData {
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

		team := teamInput.ToTeam()
		if err := s.db.Teams.Upsert(ctx, team); err != nil {
			log.Error().Err(err).Int("team_id", teamInput.TeamID).Msg("Failed to save team")
			continue
		}

		savedTeams++
	}
	log.Info().Int("count", savedTeams).Msg("Teams saved to database")

	// Fetch and upsert stadiums (if client has stadium support)
	stadiumsData, err := s.client.FetchStadiums(ctx)
	if err != nil {
		return fmt.Errorf("failed to fetch stadiums: %w", err)
	}
	log.Info().Int("count", len(stadiumsData)).Msg("Stadiums fetched")

	// Update stadiums
	savedStadiums := 0
	for _, stadiumData := range stadiumsData {
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

		stadium := stadiumInput.ToStadium()
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

		_, err = s.db.Pool.Exec(ctx, query,
			stadium.StadiumID, stadium.Name, stadium.City, stadium.State,
			stadium.Country, stadium.Capacity, stadium.Surface,
		)
		if err != nil {
			log.Error().Err(err).Int("stadium_id", stadiumInput.StadiumID).Msg("Failed to save stadium")
			continue
		}

		savedStadiums++
	}
	log.Info().Int("count", savedStadiums).Msg("Stadiums saved to database")

	log.Info().Msg("Static data refresh complete")
	return nil
}

// updateGameData updates data for a specific game
// Fetches both scores and odds
func (s *Scheduler) updateGameData(ctx context.Context, gameID int) error {
	log.Debug().Int("game_id", gameID).Msg("Updating game data")

	// Get game from database
	game, err := s.db.Games.GetByGameID(ctx, gameID)
	if err != nil {
		return fmt.Errorf("failed to get game: %w", err)
	}

	// Fetch odds from multiple sources
	// Sharp books
	sharpOddsData, err := s.client.FetchBettingMarketsByGame(ctx, gameID, &client.OddsOptions{
		Groups: string(client.GroupSharp),
	})
	if err != nil {
		log.Error().Err(err).Int("game_id", gameID).Msg("Failed to fetch sharp odds")
	} else {
		log.Debug().Int("game_id", gameID).Int("markets", len(sharpOddsData)).Msg("Sharp odds fetched")

		// Save sharp odds to database
		for _, oddsData := range sharpOddsData {
			jsonData, err := json.Marshal(oddsData)
			if err != nil {
				log.Warn().Err(err).Msg("Failed to marshal odds data")
				continue
			}

			var oddsInput models.OddsInput
			if err := json.Unmarshal(jsonData, &oddsInput); err != nil {
				log.Warn().Err(err).Msg("Failed to unmarshal odds data")
				continue
			}

			odds := oddsInput.ToOdds(game.ID)
			if err := s.db.Odds.TrackAndSaveOdds(ctx, odds); err != nil {
				log.Error().Err(err).Int("game_id", gameID).Msg("Failed to save sharp odds")
				continue
			}

			log.Debug().
				Int("game_id", gameID).
				Str("sportsbook", odds.SportsbookID).
				Str("market", odds.MarketType).
				Msg("Sharp odds saved successfully")
		}
	}

	// Public books
	publicOddsData, err := s.client.FetchBettingMarketsByGame(ctx, gameID, &client.OddsOptions{
		Groups: string(client.GroupMajorUS),
	})
	if err != nil {
		log.Error().Err(err).Int("game_id", gameID).Msg("Failed to fetch public odds")
	} else {
		log.Debug().Int("game_id", gameID).Int("markets", len(publicOddsData)).Msg("Public odds fetched")

		// Save public odds to database
		for _, oddsData := range publicOddsData {
			jsonData, err := json.Marshal(oddsData)
			if err != nil {
				log.Warn().Err(err).Msg("Failed to marshal odds data")
				continue
			}

			var oddsInput models.OddsInput
			if err := json.Unmarshal(jsonData, &oddsInput); err != nil {
				log.Warn().Err(err).Msg("Failed to unmarshal odds data")
				continue
			}

			odds := oddsInput.ToOdds(game.ID)
			if err := s.db.Odds.TrackAndSaveOdds(ctx, odds); err != nil {
				log.Error().Err(err).Int("game_id", gameID).Msg("Failed to save public odds")
				continue
			}

			log.Debug().
				Int("game_id", gameID).
				Str("sportsbook", odds.SportsbookID).
				Str("market", odds.MarketType).
				Msg("Public odds saved successfully")
		}
	}

	log.Debug().Int("game_id", gameID).Msg("Game data updated successfully")
	return nil
}
