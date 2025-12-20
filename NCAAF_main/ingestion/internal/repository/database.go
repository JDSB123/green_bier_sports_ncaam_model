package repository

import (
	"context"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/rs/zerolog/log"
)

// Database holds the database connection pool and provides access to repositories
type Database struct {
	Pool *pgxpool.Pool

	// Repositories
	Teams       *TeamRepository
	Games       *GameRepository
	Odds        *OddsRepository
	Stats       *StatsRepository
	Predictions *PredictionRepository
}

// Config holds database configuration
type Config struct {
	Host     string
	Port     string
	User     string
	Password string
	Database string
	SSLMode  string
}

// NewDatabase creates a new database connection pool and initializes repositories
func NewDatabase(ctx context.Context, cfg Config) (*Database, error) {
	// Build connection string
	dsn := fmt.Sprintf(
		"postgres://%s:%s@%s:%s/%s?sslmode=%s",
		cfg.User,
		cfg.Password,
		cfg.Host,
		cfg.Port,
		cfg.Database,
		cfg.SSLMode,
	)

	// Configure connection pool
	poolConfig, err := pgxpool.ParseConfig(dsn)
	if err != nil {
		return nil, fmt.Errorf("failed to parse database config: %w", err)
	}

	// Set pool configuration
	poolConfig.MaxConns = 25
	poolConfig.MinConns = 5
	poolConfig.MaxConnLifetime = time.Hour
	poolConfig.MaxConnIdleTime = 30 * time.Minute
	poolConfig.HealthCheckPeriod = time.Minute

	// Create connection pool
	pool, err := pgxpool.NewWithConfig(ctx, poolConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to create connection pool: %w", err)
	}

	// Test connection
	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	log.Info().
		Str("host", cfg.Host).
		Str("port", cfg.Port).
		Str("database", cfg.Database).
		Msg("Successfully connected to database")

	// Initialize database with repositories
	db := &Database{
		Pool: pool,
	}

	// Initialize repositories
	db.Teams = &TeamRepository{db: db}
	db.Games = &GameRepository{db: db}
	db.Odds = &OddsRepository{db: db}
	db.Stats = &StatsRepository{db: db}
	db.Predictions = &PredictionRepository{db: db}

	return db, nil
}

// Close closes the database connection pool
func (db *Database) Close() {
	if db.Pool != nil {
		db.Pool.Close()
		log.Info().Msg("Database connection pool closed")
	}
}

// Health checks if the database is healthy
func (db *Database) Health(ctx context.Context) error {
	ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()

	if err := db.Pool.Ping(ctx); err != nil {
		return fmt.Errorf("database health check failed: %w", err)
	}

	return nil
}

// PoolStats returns database pool statistics
func (db *Database) PoolStats() map[string]interface{} {
	stat := db.Pool.Stat()
	return map[string]interface{}{
		"total_conns":    stat.TotalConns(),
		"acquired_conns": stat.AcquiredConns(),
		"idle_conns":     stat.IdleConns(),
		"max_conns":      stat.MaxConns(),
	}
}
