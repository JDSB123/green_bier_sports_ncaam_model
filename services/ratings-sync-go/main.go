// NCAA Basketball Ratings Sync Service v6.0
//
// Fetches daily team ratings from Barttorvik and stores in PostgreSQL.
// Runs as a cron job (daily at 6 AM ET) or on-demand.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"math/rand"
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
	BackfillFrom int // Optional: starting season year for backfill
	BackfillTo   int // Optional: ending season year for backfill
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

	// Perform request with exponential backoff + jitter for transient failures
	resp, err := doRequestWithRetry(ctx, req, 5)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	// Barttorvik returns array-of-arrays, not array-of-objects
	// Format: [[rank, team, conf, record, adjoe, adjoe_rank, adjde, adjde_rank, ...], ...]
	var rawTeams [][]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&rawTeams); err != nil {
		return nil, fmt.Errorf("decoding response: %w", err)
	}

	var teams []BarttorkvikTeam
	for _, raw := range rawTeams {
		// 2025-26 season: Barttorvik returns 45 fields (indices 0-44)
		// AdjTempo is at index 44 (last element)
		if len(raw) < 25 {
			continue // Skip incomplete records - need at least basic metrics
		}

		// Parse wins/losses from record string "W-L" at index 3
		wins, losses := parseRecord(toString(raw[3]))

		// Extract Barttorvik metrics
		// Array indices for 2026 season structure:
		// [0]=Rank, [1]=Team, [2]=Conf, [3]=Record, [4]=AdjOE, [5]=AdjOE Rank,
		// [6]=AdjDE, [7]=AdjDE Rank, [8]=Barthag, [9]=Barthag Rank,
		// [10]=EFG%, [11]=EFGD%, [12]=TOR, [13]=TORD, [14]=RoadRec (string),
		// ... [44]=AdjTempo (last element, variable position)

		// Safely get AdjTempo - it's typically the last numeric value
		adjTempo := 70.0 // Default tempo
		if len(raw) >= 45 {
			adjTempo = toFloat(raw[44])
		} else if len(raw) >= 42 {
			adjTempo = toFloat(raw[len(raw)-1])
		}

		// WAB is not reliably present in 2026 format
		wab := 0.0
		if len(raw) >= 46 {
			wab = toFloat(raw[45])
		}

		team := BarttorkvikTeam{
			// Core identifiers
			Rank: toInt(raw[0]),
			Team: toString(raw[1]),
			Conf: toString(raw[2]),

			// Efficiency ratings (primary prediction inputs)
			AdjOE:    toFloat(raw[4]),
			AdjDE:    toFloat(raw[6]),
			AdjTempo: adjTempo,

			// Record
			Wins:   wins,
			Losses: losses,
			G:      wins + losses,

			// Quality metrics
			Barthag: toFloat(raw[8]),
			WAB:     wab,

			// Four Factors - Shooting
			EFG:  toFloat(raw[10]),
			EFGD: toFloat(raw[11]),

			// Four Factors - Turnovers
			TOR:  toFloat(raw[12]),
			TORD: toFloat(raw[13]),

			// Four Factors - Rebounding (indices shifted due to road record string)
			ORB: toFloat(raw[15]),
			DRB: toFloat(raw[16]),

			// Four Factors - Free Throws
			FTR:  toFloat(raw[17]),
			FTRD: toFloat(raw[18]),

			// Shooting breakdown
			TwoP:     toFloat(raw[19]),
			TwoPD:    toFloat(raw[20]),
			ThreeP:   toFloat(raw[21]),
			ThreePD:  toFloat(raw[22]),
			ThreePR:  toFloat(raw[23]),
			ThreePRD: toFloat(raw[24]),
		}
		teams = append(teams, team)
	}

	r.logger.Info("Fetched ratings", zap.Int("team_count", len(teams)))
	return teams, nil
}

// doRequestWithRetry executes an HTTP request with retries on transient errors.
// Retries on network errors, 429 Too Many Requests, and 5xx status codes.
func doRequestWithRetry(ctx context.Context, req *http.Request, maxAttempts int) (*http.Response, error) {
	client := &http.Client{Timeout: 30 * time.Second}
	var lastErr error

	// Randomize jitter
	rand.Seed(time.Now().UnixNano())

	for attempt := 1; attempt <= maxAttempts; attempt++ {
		// Clone the request for each attempt (required by net/http)
		attemptReq := req.Clone(ctx)

		resp, err := client.Do(attemptReq)

		// Success
		if err == nil && resp != nil && resp.StatusCode == http.StatusOK {
			return resp, nil
		}

		// Determine if we should retry
		retry := false
		if err != nil {
			lastErr = err
			retry = true
		}
		if resp != nil {
			// Retry on rate limiting or server errors
			if resp.StatusCode == http.StatusTooManyRequests || resp.StatusCode >= 500 {
				retry = true
			}
		}

		// If not retryable or we've exhausted attempts, return
		if !retry || attempt == maxAttempts {
			if err != nil {
				return nil, fmt.Errorf("fetching ratings: %w", err)
			}
			if resp != nil {
				return resp, fmt.Errorf("unexpected status code: %d", resp.StatusCode)
			}
			return nil, fmt.Errorf("request failed with no response: %v", lastErr)
		}

		// Compute delay: exponential backoff with cap, honor Retry-After when provided
		delay := time.Duration(1<<uint(attempt-1)) * time.Second // 1s,2s,4s,8s,16s
		if resp != nil {
			if ra := resp.Header.Get("Retry-After"); ra != "" {
				if secs, parseErr := strconv.Atoi(ra); parseErr == nil {
					delay = time.Duration(secs) * time.Second
				}
			}
			// Close body before retrying to avoid leaks
			resp.Body.Close()
		}
		// Add small jitter (0-250ms) to reduce thundering herd
		jitter := time.Duration(rand.Intn(250)) * time.Millisecond

		// Wait or abort if context cancelled
		select {
		case <-time.After(delay + jitter):
			// continue to next attempt
		case <-ctx.Done():
			return nil, ctx.Err()
		}
	}

	return nil, fmt.Errorf("all %d attempts failed: %v", maxAttempts, lastErr)
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

			// Build raw payload JSON capturing metrics for audit/compatibility
			rawPayload := map[string]any{
				"rank": team.Rank,
				"team": team.Team,
				"conf": team.Conf,
				"wins": team.Wins,
				"losses": team.Losses,
				"g": team.G,
				"adjoe": team.AdjOE,
				"adjde": team.AdjDE,
				"barthag": team.Barthag,
				"efg_o": team.EFG,
				"efg_d": team.EFGD,
				"tor": team.TOR,
				"tord": team.TORD,
				"orb": team.ORB,
				"drb": team.DRB,
				"ftr": team.FTR,
				"ftrd": team.FTRD,
				"2p_o": team.TwoP,
				"2p_d": team.TwoPD,
				"3p_o": team.ThreeP,
				"3p_d": team.ThreePD,
				"3pr": team.ThreePR,
				"3prd": team.ThreePRD,
				"adj_t": team.AdjTempo,
				"wab": team.WAB,
			}

			// Insert or update rating with ALL Barttorvik metrics + raw payload
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
					barthag, wab,
					-- Raw payload for audit/compatibility
					raw_barttorvik
			) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
				$11, $12, $13, $14, $15, $16, $17, $18,
					$19, $20, $21, $22, $23, $24, $25, $26,
					$27)
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
					wab = EXCLUDED.wab,
					-- Raw payload
					raw_barttorvik = EXCLUDED.raw_barttorvik
		`, teamID, today, team.AdjOE, team.AdjDE, team.AdjTempo,
			team.AdjOE-team.AdjDE, team.Rank, team.Wins, team.Losses, team.G,
			// Four Factors
			team.EFG, team.EFGD, team.TOR, team.TORD, team.ORB, team.DRB, team.FTR, team.FTRD,
			// Shooting breakdown
			team.TwoP, team.TwoPD, team.ThreeP, team.ThreePD, team.ThreePR, team.ThreePRD,
			// Quality metrics
				team.Barthag, team.WAB,
				// Raw payload
				rawPayload)

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
		r.logger.Error("Fetch ratings failed", zap.Error(err))
		// Alert placeholder
		fmt.Println("ALERT: Fetch ratings failed: " + err.Error())
		return fmt.Errorf("fetching ratings: %w", err)
	}

	if err := r.StoreRatings(ctx, teams); err != nil {
		r.logger.Error("Store ratings failed", zap.Error(err))
		// Alert placeholder
		fmt.Println("ALERT: Store ratings failed: " + err.Error())
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

	// Sport-parameterized database configuration (enables multi-sport deployment)
	sport := os.Getenv("SPORT")
	if sport == "" {
		sport = "ncaam"
	}
	dbUser := os.Getenv("DB_USER")
	if dbUser == "" {
		dbUser = sport
	}
	dbName := os.Getenv("DB_NAME")
	if dbName == "" {
		dbName = sport
	}
	dbHost := os.Getenv("DB_HOST")
	if dbHost == "" {
		dbHost = "postgres"
	}
	dbPort := os.Getenv("DB_PORT")
	if dbPort == "" {
		dbPort = "5432"
	}

	databaseURL := os.Getenv("DATABASE_URL")
	if databaseURL == "" {
		// Read database password from Docker secret file - REQUIRED in Docker Compose
		dbPassword := readSecretFile("/run/secrets/db_password", "db_password")
		databaseURL = fmt.Sprintf("postgresql://%s:%s@%s:%s/%s", dbUser, dbPassword, dbHost, dbPort, dbName)
	}

	config := Config{
		DatabaseURL: databaseURL,
		Season:      getCurrentSeason(),
		RunOnce:     os.Getenv("RUN_ONCE") == "true",
		BackfillFrom: 0,
		BackfillTo:   0,
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

		// Optional backfill range: BACKFILL_SEASONS="2015-2025" or "2018"
		if bf := os.Getenv("BACKFILL_SEASONS"); bf != "" {
			parts := strings.Split(bf, "-")
			if len(parts) == 2 {
				if from, err := strconv.Atoi(strings.TrimSpace(parts[0])); err == nil {
					config.BackfillFrom = from
				}
				if to, err := strconv.Atoi(strings.TrimSpace(parts[1])); err == nil {
					config.BackfillTo = to
				}
			} else if len(parts) == 1 {
				if yr, err := strconv.Atoi(strings.TrimSpace(parts[0])); err == nil {
					config.BackfillFrom = yr
					config.BackfillTo = yr
				}
			}

			if config.BackfillFrom != 0 && config.BackfillTo != 0 {
				start := config.BackfillFrom
				end := config.BackfillTo
				if start > end {
					start, end = end, start
				}
				for season := start; season <= end; season++ {
					logger.Info("Backfill season", zap.Int("season", season))
					sync.config.Season = season
					if err := sync.Sync(ctx); err != nil {
						logger.Error("Backfill sync failed", zap.Int("season", season), zap.Error(err))
					}
				}
				logger.Info("Backfill completed", zap.Int("from", start), zap.Int("to", end))
				return
			}
		}

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
