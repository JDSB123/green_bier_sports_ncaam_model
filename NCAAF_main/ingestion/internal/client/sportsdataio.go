package client

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/rs/zerolog/log"
)

// Sportsbook represents individual sportsbook IDs
type Sportsbook string

const (
	DraftKings        Sportsbook = "1100"
	FanDuel           Sportsbook = "1101"
	PointsBet         Sportsbook = "1102"
	BetMGM            Sportsbook = "1103"
	Caesars           Sportsbook = "1104"
	Pinnacle          Sportsbook = "1105"
	Circa             Sportsbook = "1106"
	Bet365            Sportsbook = "1107"
	Tipico            Sportsbook = "1109"
	Parx              Sportsbook = "1113"
	ESPNBet           Sportsbook = "1114"
	SportsIllustrated Sportsbook = "1115"
	Fanatics          Sportsbook = "1116"
	Bovada            Sportsbook = "1117"
	BetOnline         Sportsbook = "1118"
	Bookmaker         Sportsbook = "1119"
	FiveDimes         Sportsbook = "1120"
)

// SportsbookGroup represents sportsbook group IDs
type SportsbookGroup string

const (
	GroupConsensus     SportsbookGroup = "G1000"
	GroupMajorUS       SportsbookGroup = "G1001"
	GroupSharp         SportsbookGroup = "G1002"
	GroupInternational SportsbookGroup = "G1003"
	GroupRegionalPANJ  SportsbookGroup = "G1004"
	GroupMedia         SportsbookGroup = "G1005"
	GroupOffshoreSharp SportsbookGroup = "G1006"
	GroupDFS           SportsbookGroup = "G1007"
	GroupProphetX      SportsbookGroup = "G1008"
	GroupMatchbook     SportsbookGroup = "G1009"
)

// Client is the SportsDataIO API client
type Client struct {
	baseURL     string
	apiKey      string
	httpClient  *http.Client
	rateLimiter chan struct{} // Rate limiting semaphore
	maxRetries  int
	retryDelay  time.Duration
}

// NewClient creates a new SportsDataIO API client with optimizations
func NewClient(baseURL, apiKey string, timeout time.Duration) *Client {
	// Create rate limiter (max 20 concurrent requests, burst of 20)
	rateLimiter := make(chan struct{}, 20)
	for i := 0; i < 20; i++ {
		rateLimiter <- struct{}{}
	}

	return &Client{
		baseURL:     baseURL,
		apiKey:      apiKey,
		rateLimiter: rateLimiter,
		maxRetries:  3,
		retryDelay:  1 * time.Second,
		httpClient: &http.Client{
			Timeout: timeout,
			Transport: &http.Transport{
				MaxIdleConns:        100,
				MaxIdleConnsPerHost: 10,
				IdleConnTimeout:     90 * time.Second,
			},
		},
	}
}

// get performs a GET request to the SportsDataIO API with retry logic and rate limiting
func (c *Client) get(ctx context.Context, path string, params map[string]string) ([]byte, error) {
	url := fmt.Sprintf("%s/%s", c.baseURL, path)

	var lastErr error
	for attempt := 0; attempt <= c.maxRetries; attempt++ {
		if attempt > 0 {
			// Exponential backoff: 1s, 2s, 4s
			backoff := c.retryDelay * time.Duration(1<<uint(attempt-1))
			log.Info().
				Str("url", url).
				Int("attempt", attempt).
				Dur("backoff", backoff).
				Msg("Retrying API request after backoff")

			select {
			case <-ctx.Done():
				return nil, ctx.Err()
			case <-time.After(backoff):
			}
		}

		// Rate limiting: acquire semaphore
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-c.rateLimiter:
			defer func() { c.rateLimiter <- struct{}{} }()
		}

		req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
		if err != nil {
			return nil, fmt.Errorf("failed to create request: %w", err)
		}

		// Add headers
		req.Header.Set("Ocp-Apim-Subscription-Key", c.apiKey)
		req.Header.Set("Accept", "application/json")
		req.Header.Set("User-Agent", "NCAAF-v5.0/1.0")

		// Add query parameters
		if len(params) > 0 {
			q := req.URL.Query()
			for key, value := range params {
				q.Add(key, value)
			}
			req.URL.RawQuery = q.Encode()
		}

		log.Debug().
			Str("url", url).
			Str("method", req.Method).
			Int("attempt", attempt+1).
			Msg("Making API request")

		resp, err := c.httpClient.Do(req)
		if err != nil {
			lastErr = fmt.Errorf("API request failed: %w", err)
			// Retry on network errors
			if attempt < c.maxRetries {
				continue
			}
			return nil, lastErr
		}
		defer resp.Body.Close()

		body, err := io.ReadAll(resp.Body)
		if err != nil {
			lastErr = fmt.Errorf("failed to read response body: %w", err)
			if attempt < c.maxRetries {
				continue
			}
			return nil, lastErr
		}

		// Handle different status codes
		switch resp.StatusCode {
		case http.StatusOK:
			// Success
			log.Debug().
				Str("url", url).
				Int("status", resp.StatusCode).
				Int("size", len(body)).
				Msg("API request successful")
			return body, nil

		case http.StatusTooManyRequests, http.StatusServiceUnavailable, http.StatusGatewayTimeout:
			// Retryable errors
			lastErr = fmt.Errorf("API returned retryable status %d: %s", resp.StatusCode, string(body))
			if attempt < c.maxRetries {
				log.Warn().
					Str("url", url).
					Int("status", resp.StatusCode).
					Int("attempt", attempt+1).
					Msg("Received retryable error, will retry")
				continue
			}
			return nil, lastErr

		case http.StatusUnauthorized, http.StatusForbidden:
			// Don't retry auth errors
			return nil, fmt.Errorf("API authentication failed (status %d): %s", resp.StatusCode, string(body))

		default:
			// Other errors - don't retry
			return nil, fmt.Errorf("API returned status %d: %s", resp.StatusCode, string(body))
		}
	}

	return nil, lastErr
}

// FetchCurrentSeason fetches the current season year
func (c *Client) FetchCurrentSeason(ctx context.Context) (int, error) {
	body, err := c.get(ctx, "scores/json/CurrentSeason", nil)
	if err != nil {
		return 0, fmt.Errorf("failed to fetch current season: %w", err)
	}

	var season int
	if err := json.Unmarshal(body, &season); err != nil {
		return 0, fmt.Errorf("failed to unmarshal season: %w", err)
	}

	return season, nil
}

// FetchCurrentWeek fetches the current week number
func (c *Client) FetchCurrentWeek(ctx context.Context) (int, error) {
	body, err := c.get(ctx, "scores/json/CurrentWeek", nil)
	if err != nil {
		return 0, fmt.Errorf("failed to fetch current week: %w", err)
	}

	var week int
	if err := json.Unmarshal(body, &week); err != nil {
		return 0, fmt.Errorf("failed to unmarshal week: %w", err)
	}

	return week, nil
}

// FetchTeams fetches all teams
func (c *Client) FetchTeams(ctx context.Context) ([]map[string]interface{}, error) {
	body, err := c.get(ctx, "scores/json/Teams", nil)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch teams: %w", err)
	}

	var teams []map[string]interface{}
	if err := json.Unmarshal(body, &teams); err != nil {
		return nil, fmt.Errorf("failed to unmarshal teams: %w", err)
	}

	return teams, nil
}

// FetchGames fetches game schedule for a season
func (c *Client) FetchGames(ctx context.Context, season string) ([]map[string]interface{}, error) {
	path := fmt.Sprintf("scores/json/Games/%s", season)
	body, err := c.get(ctx, path, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch games: %w", err)
	}

	var games []map[string]interface{}
	if err := json.Unmarshal(body, &games); err != nil {
		return nil, fmt.Errorf("failed to unmarshal games: %w", err)
	}

	return games, nil
}

// FetchTeamSeasonStats fetches team season statistics
func (c *Client) FetchTeamSeasonStats(ctx context.Context, season string) ([]map[string]interface{}, error) {
	path := fmt.Sprintf("scores/json/TeamSeasonStats/%s", season)
	body, err := c.get(ctx, path, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch team season stats: %w", err)
	}

	var stats []map[string]interface{}
	if err := json.Unmarshal(body, &stats); err != nil {
		return nil, fmt.Errorf("failed to unmarshal team season stats: %w", err)
	}

	return stats, nil
}

// FetchGameOddsByWeek fetches game odds for a specific week
func (c *Client) FetchGameOddsByWeek(ctx context.Context, season string, week int, opts *OddsOptions) ([]map[string]interface{}, error) {
	path := fmt.Sprintf("odds/json/GameOddsByWeek/%s/%d", season, week)

	params := make(map[string]string)
	if opts != nil {
		if opts.Groups != "" {
			params["groups"] = opts.Groups
		}
		if opts.Books != "" {
			params["books"] = opts.Books
		}
		if opts.Markets != "" {
			params["markets"] = opts.Markets
		}
		if opts.OddsFormat != "" {
			params["oddsFormat"] = opts.OddsFormat
		}
	}

	body, err := c.get(ctx, path, params)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch game odds: %w", err)
	}

	var odds []map[string]interface{}
	if err := json.Unmarshal(body, &odds); err != nil {
		return nil, fmt.Errorf("failed to unmarshal game odds: %w", err)
	}

	return odds, nil
}

// FetchBettingMarketsByGame fetches betting markets for a specific game
func (c *Client) FetchBettingMarketsByGame(ctx context.Context, gameID int, opts *OddsOptions) ([]map[string]interface{}, error) {
	path := fmt.Sprintf("odds/json/BettingMarketsByGameID/%d", gameID)

	params := make(map[string]string)
	if opts != nil {
		if opts.Groups != "" {
			params["groups"] = opts.Groups
		}
		if opts.Books != "" {
			params["books"] = opts.Books
		}
		if opts.Markets != "" {
			params["markets"] = opts.Markets
		}
	}

	body, err := c.get(ctx, path, params)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch betting markets: %w", err)
	}

	var markets []map[string]interface{}
	if err := json.Unmarshal(body, &markets); err != nil {
		return nil, fmt.Errorf("failed to unmarshal betting markets: %w", err)
	}

	return markets, nil
}

// FetchLineMovementByGame fetches line movement for a specific game
func (c *Client) FetchLineMovementByGame(ctx context.Context, gameID int, opts *OddsOptions) ([]map[string]interface{}, error) {
	path := fmt.Sprintf("odds/json/BettingMarketLinesByGameID/%d", gameID)

	params := make(map[string]string)
	if opts != nil {
		if opts.Groups != "" {
			params["groups"] = opts.Groups
		}
		if opts.Books != "" {
			params["books"] = opts.Books
		}
		if opts.Markets != "" {
			params["markets"] = opts.Markets
		}
	}

	body, err := c.get(ctx, path, params)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch line movement: %w", err)
	}

	var lineMovement []map[string]interface{}
	if err := json.Unmarshal(body, &lineMovement); err != nil {
		return nil, fmt.Errorf("failed to unmarshal line movement: %w", err)
	}

	return lineMovement, nil
}

// FetchBoxScoresByWeek fetches box scores for a specific week
func (c *Client) FetchBoxScoresByWeek(ctx context.Context, season string, week int) ([]map[string]interface{}, error) {
	path := fmt.Sprintf("stats/json/BoxScoresByWeek/%s/%d", season, week)

	body, err := c.get(ctx, path, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch box scores: %w", err)
	}

	var boxScores []map[string]interface{}
	if err := json.Unmarshal(body, &boxScores); err != nil {
		return nil, fmt.Errorf("failed to unmarshal box scores: %w", err)
	}

	return boxScores, nil
}

// FetchStadiums fetches stadium information
func (c *Client) FetchStadiums(ctx context.Context) ([]map[string]interface{}, error) {
	body, err := c.get(ctx, "scores/json/Stadiums", nil)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch stadiums: %w", err)
	}

	var stadiums []map[string]interface{}
	if err := json.Unmarshal(body, &stadiums); err != nil {
		return nil, fmt.Errorf("failed to unmarshal stadiums: %w", err)
	}

	return stadiums, nil
}

// OddsOptions represents options for fetching odds
type OddsOptions struct {
	Groups     string
	Books      string
	Markets    string
	OddsFormat string
}

// Helper functions for common queries

// FetchSharpOdds fetches sharp book odds (Pinnacle + Circa)
func (c *Client) FetchSharpOdds(ctx context.Context, season string, week int) ([]map[string]interface{}, error) {
	return c.FetchGameOddsByWeek(ctx, season, week, &OddsOptions{
		Groups: string(GroupSharp),
	})
}

// FetchPublicOdds fetches public book odds (Major US books)
func (c *Client) FetchPublicOdds(ctx context.Context, season string, week int) ([]map[string]interface{}, error) {
	return c.FetchGameOddsByWeek(ctx, season, week, &OddsOptions{
		Groups: string(GroupMajorUS),
	})
}

// FetchConsensusOdds fetches consensus odds across all books
func (c *Client) FetchConsensusOdds(ctx context.Context, season string, week int) ([]map[string]interface{}, error) {
	return c.FetchGameOddsByWeek(ctx, season, week, &OddsOptions{
		Groups: string(GroupConsensus),
	})
}
