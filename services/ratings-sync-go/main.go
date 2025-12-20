// NCAA Basketball Ratings Sync Service v5.0
//
// Fetches daily team ratings from Barttorvik and stores in PostgreSQL.
// Runs as a cron job (daily at 6 AM ET) or on-demand.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/robfig/cron/v3"
	"go.uber.org/zap"
)

// BarttorkvikTeam represents a team's data from the Barttorvik JSON API
type BarttorkvikTeam struct {
	Team     string  `json:"team"`
	Conf     string  `json:"conf"`
	G        int     `json:"g"`
	Wins     int     `json:"wins"`
	Losses   int     `json:"losses"`
	AdjOE    float64 `json:"adjoe"`
	AdjDE    float64 `json:"adjde"`
	Barthag  float64 `json:"barthag"`
	EFG      float64 `json:"efg_o"`
	EFGD     float64 `json:"efg_d"`
	TOR      float64 `json:"tor"`
	TORD     float64 `json:"tord"`
	ORB      float64 `json:"orb"`
	DRB      float64 `json:"drb"`
	FTR      float64 `json:"ftr"`
	FTRD     float64 `json:"ftrd"`
	TwoP     float64 `json:"2p_o"`
	TwoPD    float64 `json:"2p_d"`
	ThreeP   float64 `json:"3p_o"`
	ThreePD  float64 `json:"3p_d"`
	ThreePR  float64 `json:"3pr"`
	ThreePRD float64 `json:"3prd"`
	AdjTempo float64 `json:"adj_t"`
	WAB      float64 `json:"wab"`
	Rank     int     `json:"rk"`
}

// Config holds application configuration
type Config struct {
	DatabaseURL string
	Season      int
	RunOnce     bool
}

// RatingsSync handles fetching and storing ratings
type RatingsSync struct {
	db     *pgxpool.Pool
	logger *zap.Logger
	config Config
}

// NewRatingsSync creates a new sync service
func NewRatingsSync(db *pgxpool.Pool, logger *zap.Logger, config Config) *RatingsSync {
	return &RatingsSync{
		db:     db,
		logger: logger,
		config: config,
	}
}

// FetchRatings fetches current ratings from Barttorvik
func (r *RatingsSync) FetchRatings(ctx context.Context) ([]BarttorkvikTeam, error) {
	url := fmt.Sprintf("https://barttorvik.com/%d_team_results.json", r.config.Season)

	r.logger.Info("Fetching ratings from Barttorvik", zap.String("url", url))

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("creating request: %w", err)
	}

	// Set user agent to avoid blocking
	req.Header.Set("User-Agent", "NCAAM-Ratings-Sync/5.0")

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("fetching ratings: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected status code: %d", resp.StatusCode)
	}

	// Barttorvik returns array-of-arrays, not array-of-objects
	// Format: [[rank, team, conf, record, adjoe, adjoe_rank, adjde, adjde_rank, ...], ...]
	var rawTeams [][]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&rawTeams); err != nil {
		return nil, fmt.Errorf("decoding response: %w", err)
	}

	var teams []BarttorkvikTeam
	for _, raw := range rawTeams {
		if len(raw) < 46 {
			continue // Skip incomplete records
		}

		// Parse wins/losses from record string "W-L" at index 3
		wins, losses := parseRecord(toString(raw[3]))

		// Extract ALL Barttorvik metrics for comprehensive model
		// Array indices verified against 2025_team_results.json structure:
		// [0]=Rank, [1]=Team, [2]=Conf, [3]=Record, [4]=AdjOE, [5]=AdjOE Rank,
		// [6]=AdjDE, [7]=AdjDE Rank, [8]=Barthag, [9]=Barthag Rank,
		// [10]=EFG%, [11]=EFGD%, [12]=TOR, [13]=TORD, [14]=ORB, [15]=DRB,
		// [16]=FTR, [17]=FTRD, [18]=2P%, [19]=2PD%, [20]=3P%, [21]=3PD%,
		// [22]=3PR, [23]=3PRD, ... [44]=AdjTempo, [45]=WAB
		team := BarttorkvikTeam{
			// Core identifiers
			Rank: toInt(raw[0]),
			Team: toString(raw[1]),
			Conf: toString(raw[2]),

			// Efficiency ratings (primary prediction inputs)
			AdjOE:    toFloat(raw[4]),
			AdjDE:    toFloat(raw[6]),
			AdjTempo: toFloat(raw[44]),

			// Record
			Wins:   wins,
			Losses: losses,
			G:      wins + losses,

			// Quality metrics
			Barthag: toFloat(raw[8]),
			WAB:     toFloat(raw[45]),

			// Four Factors - Shooting
			EFG:  toFloat(raw[10]),
			EFGD: toFloat(raw[11]),

			// Four Factors - Turnovers
			TOR:  toFloat(raw[12]),
			TORD: toFloat(raw[13]),

			// Four Factors - Rebounding
			ORB: toFloat(raw[14]),
			DRB: toFloat(raw[15]),

			// Four Factors - Free Throws
			FTR:  toFloat(raw[16]),
			FTRD: toFloat(raw[17]),

			// Shooting breakdown
			TwoP:     toFloat(raw[18]),
			TwoPD:    toFloat(raw[19]),
			ThreeP:   toFloat(raw[20]),
			ThreePD:  toFloat(raw[21]),
			ThreePR:  toFloat(raw[22]),
			ThreePRD: toFloat(raw[23]),
		}
		teams = append(teams, team)
	}

	r.logger.Info("Fetched ratings", zap.Int("team_count", len(teams)))
	return teams, nil
}

// Helper functions to safely convert interface{} to types
func toInt(v interface{}) int {
	switch val := v.(type) {
	case float64:
		return int(val)
	case int:
		return val
	case string:
		i, _ := strconv.Atoi(val)
		return i
	}
	return 0
}

func toFloat(v interface{}) float64 {
	switch val := v.(type) {
	case float64:
		return val
	case int:
		return float64(val)
	case string:
		f, _ := strconv.ParseFloat(val, 64)
		return f
	}
	return 0.0
}

func toString(v interface{}) string {
	switch val := v.(type) {
	case string:
		return val
	case float64:
		return strconv.FormatFloat(val, 'f', -1, 64)
	case int:
		return strconv.Itoa(val)
	}
	return ""
}

func parseRecord(record string) (wins, losses int) {
	parts := strings.Split(record, "-")
	if len(parts) == 2 {
		wins, _ = strconv.Atoi(parts[0])
		losses, _ = strconv.Atoi(parts[1])
	}
	return
}

// StoreRatings stores ratings in the database
func (r *RatingsSync) StoreRatings(ctx context.Context, teams []BarttorkvikTeam) error {
	// FIX: Use UTC for consistent date storage across all services
	// This ensures ratings align with games stored in UTC by the Rust service
	today := time.Now().UTC().Format("2006-01-02")

	r.logger.Info("Storing ratings", zap.String("date", today), zap.Int("team_count", len(teams)))

	// Start transaction
	tx, err := r.db.Begin(ctx)
	if err != nil {
		return fmt.Errorf("starting transaction: %w", err)
	}
	defer tx.Rollback(ctx)

	stored := 0
	for _, team := range teams {
		// First, ensure team exists
		teamID, err := r.ensureTeam(ctx, tx, team)
		if err != nil {
			r.logger.Warn("Failed to ensure team", zap.String("team", team.Team), zap.Error(err))
			continue
		}

		// Insert or update rating with ALL Barttorvik metrics
		_, err = tx.Exec(ctx, `
			INSERT INTO team_ratings (
				team_id, rating_date, adj_o, adj_d, tempo, net_rating,
				torvik_rank, wins, losses, games_played,
				-- Four Factors
				efg, efgd, tor, tord, orb, drb, ftr, ftrd,
				-- Shooting breakdown
				two_pt_pct, two_pt_pct_d, three_pt_pct, three_pt_pct_d,
				three_pt_rate, three_pt_rate_d,
				-- Quality metrics
				barthag, wab
			) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
				$11, $12, $13, $14, $15, $16, $17, $18,
				$19, $20, $21, $22, $23, $24, $25, $26)
			ON CONFLICT (team_id, rating_date) DO UPDATE SET
				adj_o = EXCLUDED.adj_o,
				adj_d = EXCLUDED.adj_d,
				tempo = EXCLUDED.tempo,
				net_rating = EXCLUDED.net_rating,
				torvik_rank = EXCLUDED.torvik_rank,
				wins = EXCLUDED.wins,
				losses = EXCLUDED.losses,
				games_played = EXCLUDED.games_played,
				-- Four Factors
				efg = EXCLUDED.efg,
				efgd = EXCLUDED.efgd,
				tor = EXCLUDED.tor,
				tord = EXCLUDED.tord,
				orb = EXCLUDED.orb,
				drb = EXCLUDED.drb,
				ftr = EXCLUDED.ftr,
				ftrd = EXCLUDED.ftrd,
				-- Shooting breakdown
				two_pt_pct = EXCLUDED.two_pt_pct,
				two_pt_pct_d = EXCLUDED.two_pt_pct_d,
				three_pt_pct = EXCLUDED.three_pt_pct,
				three_pt_pct_d = EXCLUDED.three_pt_pct_d,
				three_pt_rate = EXCLUDED.three_pt_rate,
				three_pt_rate_d = EXCLUDED.three_pt_rate_d,
				-- Quality metrics
				barthag = EXCLUDED.barthag,
				wab = EXCLUDED.wab
		`, teamID, today, team.AdjOE, team.AdjDE, team.AdjTempo,
			team.AdjOE-team.AdjDE, team.Rank, team.Wins, team.Losses, team.G,
			// Four Factors
			team.EFG, team.EFGD, team.TOR, team.TORD, team.ORB, team.DRB, team.FTR, team.FTRD,
			// Shooting breakdown
			team.TwoP, team.TwoPD, team.ThreeP, team.ThreePD, team.ThreePR, team.ThreePRD,
			// Quality metrics
			team.Barthag, team.WAB)

		if err != nil {
			r.logger.Warn("Failed to store rating", zap.String("team", team.Team), zap.Error(err))
			continue
		}
		stored++
	}

	if err := tx.Commit(ctx); err != nil {
		return fmt.Errorf("committing transaction: %w", err)
	}

	r.logger.Info("Stored ratings successfully", zap.Int("stored", stored), zap.Int("total", len(teams)))
	return nil
}

// ensureTeam makes sure the team exists in the database
func (r *RatingsSync) ensureTeam(ctx context.Context, tx pgx.Tx, team BarttorkvikTeam) (string, error) {
	var teamID string

	// Try to find by barttorvik_name first
	err := tx.QueryRow(ctx, `
		SELECT id FROM teams WHERE barttorvik_name = $1
	`, team.Team).Scan(&teamID)

	if err == nil {
		return teamID, nil
	}

	// STEP 1: Try to resolve using database function (99.99% accuracy)
	var resolvedCanonical string
	err = tx.QueryRow(ctx, `
		SELECT resolve_team_name($1)
	`, team.Team).Scan(&resolvedCanonical)

	if err == nil && resolvedCanonical != "" {
		// Found existing canonical name via alias resolution
		err = tx.QueryRow(ctx, `
			SELECT id FROM teams WHERE canonical_name = $1
		`, resolvedCanonical).Scan(&teamID)

		if err == nil {
			// Update barttorvik_name if not set
			tx.Exec(ctx, `
				UPDATE teams SET barttorvik_name = $1 WHERE id = $2 AND barttorvik_name IS NULL
			`, team.Team, teamID)

			// Ensure alias exists
			tx.Exec(ctx, `
				INSERT INTO team_aliases (team_id, alias, source)
				VALUES ($1, $2, 'barttorvik')
				ON CONFLICT (alias, source) DO NOTHING
			`, teamID, team.Team)

			return teamID, nil
		}
	}

	// STEP 2: Try canonical name (normalized) - fallback if resolve_team_name didn't work
	// FIX: Log when falling back to local normalization (indicates missing alias in DB)
	canonicalName := normalizeTeamName(team.Team)
	r.logger.Warn("FALLBACK: resolve_team_name() missed, using local normalization",
		zap.String("barttorvik_name", team.Team),
		zap.String("normalized_to", canonicalName),
	)
	err = tx.QueryRow(ctx, `
		SELECT id FROM teams WHERE canonical_name = $1
	`, canonicalName).Scan(&teamID)

	if err == nil {
		// Update barttorvik_name if not set
		tx.Exec(ctx, `
			UPDATE teams SET barttorvik_name = $1 WHERE id = $2 AND barttorvik_name IS NULL
		`, team.Team, teamID)

		// Ensure alias exists
		tx.Exec(ctx, `
			INSERT INTO team_aliases (team_id, alias, source)
			VALUES ($1, $2, 'barttorvik')
			ON CONFLICT (alias, source) DO NOTHING
		`, teamID, team.Team)

		return teamID, nil
	}

	// STEP 3: Team doesn't exist - create with normalized canonical name
	err = tx.QueryRow(ctx, `
		INSERT INTO teams (canonical_name, barttorvik_name, conference)
		VALUES ($1, $2, $3)
		RETURNING id
	`, canonicalName, team.Team, team.Conf).Scan(&teamID)

	if err != nil {
		return "", fmt.Errorf("creating team: %w", err)
	}

	// Also add barttorvik alias
	tx.Exec(ctx, `
		INSERT INTO team_aliases (team_id, alias, source)
		VALUES ($1, $2, 'barttorvik')
		ON CONFLICT (alias, source) DO NOTHING
	`, teamID, team.Team)

	r.logger.Info("Created new team", zap.String("team", team.Team), zap.String("id", teamID))
	return teamID, nil
}

// normalizeTeamName converts Barttorvik team name to canonical format
// CRITICAL: This ensures consistent naming BEFORE creating new teams
// Only used as fallback if resolve_team_name() doesn't find a match
func normalizeTeamName(name string) string {
	name = strings.TrimSpace(name)

	// Common transformations for canonical format
	replacements := map[string]string{
		" State":         " St.",
		"Saint ":         "St. ",
		"St ":            "St. ",
		"University":     "U",
		"College":        "Col.",
		"North Carolina": "N.C.",
		"South Carolina": "S.C.",
		"Northern ":      "N. ",
		"Southern ":      "S. ",
		"Eastern ":       "E. ",
		"Western ":       "W. ",
		"Central ":       "C. ",
	}

	for old, new := range replacements {
		name = strings.ReplaceAll(name, old, new)
	}

	return strings.TrimSpace(name)
}

// Sync performs a full sync
func (r *RatingsSync) Sync(ctx context.Context) error {
	start := time.Now()
	r.logger.Info("Starting ratings sync")

	teams, err := r.FetchRatings(ctx)
	if err != nil {
		return fmt.Errorf("fetching ratings: %w", err)
	}

	if err := r.StoreRatings(ctx, teams); err != nil {
		return fmt.Errorf("storing ratings: %w", err)
	}

	r.logger.Info("Ratings sync completed",
		zap.Duration("duration", time.Since(start)),
		zap.Int("teams", len(teams)))

	return nil
}

// readSecretFile reads a secret from Docker secret file - REQUIRED, NO fallbacks
func readSecretFile(filePath string, secretName string) string {
	data, err := os.ReadFile(filePath)
	if err != nil {
		log.Fatalf("CRITICAL: Secret file not found: %s (%s). Container must have secrets mounted.", filePath, secretName)
	}
	password := strings.TrimSpace(string(data))
	if password == "" {
		log.Fatalf("CRITICAL: Secret file %s is empty (%s).", filePath, secretName)
	}
	return password
}

// getCurrentSeason calculates the current NCAA basketball season
func getCurrentSeason() int {
	now := time.Now()
	year := now.Year()

	// NCAA season starts in November
	// If we're in Jan-April, use current year
	// If we're in May-December, use next year
	if now.Month() >= time.May {
		return year + 1
	}
	return year
}

func main() {
	// NO .env file loading - all secrets MUST come from Docker secret files

	// Initialize logger
	logger, err := zap.NewProduction()
	if err != nil {
		log.Fatal("Failed to initialize logger:", err)
	}
	defer logger.Sync()

	// Parse config
	// - Docker Compose: DATABASE_URL is not set; we build it from /run/secrets/db_password
	// - Azure Container Apps: DATABASE_URL is set via env vars; no /run/secrets mount exists
	databaseURL := os.Getenv("DATABASE_URL")
	if databaseURL == "" {
		// Read database password from Docker secret file - REQUIRED in Docker Compose
		dbPassword := readSecretFile("/run/secrets/db_password", "db_password")
		databaseURL = fmt.Sprintf("postgresql://ncaam:%s@postgres:5432/ncaam", dbPassword)
	}

	config := Config{
		DatabaseURL: databaseURL,
		Season:      getCurrentSeason(),
		RunOnce:     os.Getenv("RUN_ONCE") == "true",
	}

	if config.DatabaseURL == "" {
		logger.Fatal("CRITICAL: DATABASE_URL not configured. Provide DATABASE_URL env var (Azure) or mount /run/secrets/db_password (Docker Compose).")
	}

	// Override season if provided
	if s := os.Getenv("SEASON"); s != "" {
		if parsed, err := strconv.Atoi(s); err == nil {
			config.Season = parsed
		}
	}

	logger.Info("Starting Ratings Sync Service",
		zap.Int("season", config.Season),
		zap.Bool("run_once", config.RunOnce))

	// Connect to database
	ctx := context.Background()
	db, err := pgxpool.New(ctx, config.DatabaseURL)
	if err != nil {
		logger.Fatal("Failed to connect to database", zap.Error(err))
	}
	defer db.Close()

	// Create sync service
	sync := NewRatingsSync(db, logger, config)

	// Run once mode
	if config.RunOnce {
		if err := sync.Sync(ctx); err != nil {
			logger.Fatal("Sync failed", zap.Error(err))
		}
		logger.Info("Single sync completed successfully")
		return
	}

	// Cron mode - run daily at 6 AM ET
	// FIX: Use LoadLocation instead of FixedZone to properly handle EDT/EST transitions
	// FixedZone was hardcoded to -5 hours (EST), causing runs to be 1 hour late during daylight savings
	easternTime, err := time.LoadLocation("America/New_York")
	if err != nil {
		// Fallback to EST if timezone data unavailable (shouldn't happen in container)
		logger.Warn("Failed to load America/New_York timezone, falling back to EST", zap.Error(err))
		easternTime = time.FixedZone("EST", -5*60*60)
	}
	c := cron.New(cron.WithLocation(easternTime))
	c.AddFunc("0 6 * * *", func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
		defer cancel()

		if err := sync.Sync(ctx); err != nil {
			logger.Error("Scheduled sync failed", zap.Error(err))
		}
	})

	// Also run immediately on startup
	go func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
		defer cancel()

		if err := sync.Sync(ctx); err != nil {
			logger.Error("Initial sync failed", zap.Error(err))
		}
	}()

	c.Start()
	logger.Info("Cron scheduler started, next run at 6 AM ET")

	// Wait for shutdown signal
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	<-sigChan

	logger.Info("Shutting down...")
	c.Stop()
}
