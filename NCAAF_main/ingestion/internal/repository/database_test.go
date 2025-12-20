package repository

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// Integration tests for database operations
// Run with: go test -v -tags=integration ./internal/repository/...

func setupTestDB(t *testing.T) (*Database, context.Context) {
	ctx := context.Background()

	cfg := Config{
		Host:     "localhost",
		Port:     "5432",
		Database: "ncaaf_v5_test",
		User:     "ncaaf_user",
		Password: "ncaaf_password",
		SSLMode:  "disable",
	}

	db, err := NewDatabase(ctx, cfg)
	require.NoError(t, err, "Failed to connect to test database")

	return db, ctx
}

func teardownTestDB(t *testing.T, db *Database) {
	db.Close()
}

func TestDatabaseConnection(t *testing.T) {
	db, ctx := setupTestDB(t)
	defer teardownTestDB(t, db)

	// Test health check
	err := db.Health(ctx)
	assert.NoError(t, err, "Database health check should pass")

	// Test stats
	stats := db.PoolStats()
	assert.NotNil(t, stats, "Should return connection pool stats")
	assert.GreaterOrEqual(t, stats["max_conns"].(int32), int32(1), "Should have at least 1 max connection")
}

func TestDatabasePing(t *testing.T) {
	db, ctx := setupTestDB(t)
	defer teardownTestDB(t, db)

	// Ping with timeout
	ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()

	err := db.Pool.Ping(ctx)
	assert.NoError(t, err, "Should successfully ping database")
}
