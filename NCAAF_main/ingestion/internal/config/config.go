package config

import (
	"fmt"
	"os"
	"time"

	"github.com/joho/godotenv"
	"github.com/kelseyhightower/envconfig"
)

// Config holds all application configuration
type Config struct {
	// SportsDataIO API
	SportsDataAPIKey  string        `envconfig:"SPORTSDATA_API_KEY" required:"true"`
	SportsDataBaseURL string        `envconfig:"SPORTSDATA_BASE_URL" default:"https://api.sportsdata.io/v3/cfb"`
	SportsDataTimeout time.Duration `envconfig:"SPORTSDATA_TIMEOUT" default:"30s"`

	// Database
	DatabaseHost     string `envconfig:"DATABASE_HOST" default:"localhost"`
	DatabasePort     int    `envconfig:"DATABASE_PORT" default:"5432"`
	DatabaseName     string `envconfig:"DATABASE_NAME" default:"ncaaf_v5"`
	DatabaseUser     string `envconfig:"DATABASE_USER" default:"ncaaf_user"`
	DatabasePassword string `envconfig:"DATABASE_PASSWORD" required:"true"`
	DatabaseSSLMode  string `envconfig:"DATABASE_SSL_MODE" default:"disable"`

	// Redis
	RedisHost     string `envconfig:"REDIS_HOST" default:"localhost"`
	RedisPort     int    `envconfig:"REDIS_PORT" default:"6379"`
	RedisPassword string `envconfig:"REDIS_PASSWORD" default:""`
	RedisDB       int    `envconfig:"REDIS_DB" default:"0"`

	// Application
	AppEnv   string `envconfig:"APP_ENV" default:"development"`
	LogLevel string `envconfig:"LOG_LEVEL" default:"info"`

	// Ingestion Service
	IngestionPort int `envconfig:"INGESTION_PORT" default:"8080"`

	// Worker Configuration
	WorkerInterval time.Duration `envconfig:"WORKER_INTERVAL" default:"60s"`

	// Webhook
	WebhookEnabled bool   `envconfig:"WEBHOOK_ENABLED" default:"true"`
	WebhookSecret  string `envconfig:"WEBHOOK_SECRET" default:"change_me"`

	// Scheduler
	EnableScheduler        bool   `envconfig:"ENABLE_SCHEDULER" default:"true"`
	InitialSyncEnabled     bool   `envconfig:"INITIAL_SYNC_ENABLED" default:"true"`
	NightlyRefreshCron     string `envconfig:"NIGHTLY_REFRESH_CRON" default:"0 2 * * *"`
	ActiveGamePollInterval int    `envconfig:"ACTIVE_GAME_POLL_INTERVAL" default:"60"`

	// API Rate Limiting
	APIRateLimit  int `envconfig:"API_RATE_LIMIT" default:"100"`
	APIBurstLimit int `envconfig:"API_BURST_LIMIT" default:"20"`

	// Caching TTL (in seconds)
	CacheTTLTeams       int `envconfig:"CACHE_TTL_TEAMS" default:"86400"`     // 24 hours
	CacheTTLOdds        int `envconfig:"CACHE_TTL_ODDS" default:"300"`        // 5 minutes
	CacheTTLPredictions int `envconfig:"CACHE_TTL_PREDICTIONS" default:"600"` // 10 minutes

	// Feature Flags
	EnableWebhooks              bool `envconfig:"ENABLE_WEBHOOKS" default:"true"`
	EnableLineMovementTracking  bool `envconfig:"ENABLE_LINE_MOVEMENT_TRACKING" default:"true"`
	EnableSharpPublicDivergence bool `envconfig:"ENABLE_SHARP_PUBLIC_DIVERGENCE" default:"true"`
	EnableCLVTracking           bool `envconfig:"ENABLE_CLV_TRACKING" default:"true"`

	// Monitoring
	EnableMetrics bool `envconfig:"ENABLE_METRICS" default:"true"`
	MetricsPort   int  `envconfig:"METRICS_PORT" default:"9090"`
}

// Load loads configuration from environment variables
// It first attempts to load from .env file if in development mode
func Load() (*Config, error) {
	// Try to load .env file (ignore error if doesn't exist)
	_ = godotenv.Load()

	var cfg Config
	if err := envconfig.Process("", &cfg); err != nil {
		return nil, fmt.Errorf("failed to process environment config: %w", err)
	}

	// Validate
	if err := cfg.Validate(); err != nil {
		return nil, fmt.Errorf("invalid configuration: %w", err)
	}

	return &cfg, nil
}

// Validate validates the configuration
func (c *Config) Validate() error {
	if c.SportsDataAPIKey == "" {
		return fmt.Errorf("SPORTSDATA_API_KEY is required")
	}

	if c.DatabasePassword == "" {
		return fmt.Errorf("DATABASE_PASSWORD is required")
	}

	if c.WebhookEnabled && c.WebhookSecret == "change_me" && c.AppEnv == "production" {
		return fmt.Errorf("WEBHOOK_SECRET must be changed in production")
	}

	return nil
}

// DatabaseDSN returns the PostgreSQL connection string
func (c *Config) DatabaseDSN() string {
	return fmt.Sprintf(
		"host=%s port=%d user=%s password=%s dbname=%s sslmode=%s",
		c.DatabaseHost,
		c.DatabasePort,
		c.DatabaseUser,
		c.DatabasePassword,
		c.DatabaseName,
		c.DatabaseSSLMode,
	)
}

// RedisAddr returns the Redis address
func (c *Config) RedisAddr() string {
	return fmt.Sprintf("%s:%d", c.RedisHost, c.RedisPort)
}

// IsDevelopment returns true if running in development mode
func (c *Config) IsDevelopment() bool {
	return c.AppEnv == "development"
}

// IsProduction returns true if running in production mode
func (c *Config) IsProduction() bool {
	return c.AppEnv == "production"
}

// MustLoad loads configuration or panics on error
// Use this in main() where we want to fail fast
func MustLoad() *Config {
	cfg, err := Load()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to load configuration: %v\n", err)
		os.Exit(1)
	}
	return cfg
}
