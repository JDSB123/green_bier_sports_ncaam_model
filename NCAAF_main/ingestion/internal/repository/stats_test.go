package repository

import (
	"database/sql"
	"testing"

	"ncaaf_v5/ingestion/internal/models"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestStatsRepository_Upsert(t *testing.T) {
	db, ctx := setupTestDB(t)
	defer teardownTestDB(t, db)

	// Create test team
	team := &models.Team{TeamID: 1000, TeamCode: "STAT", SchoolName: "Stats University"}
	require.NoError(t, db.Teams.Upsert(ctx, team))

	// Create season stats using actual model fields
	stats := &models.TeamSeasonStats{
		TeamID:               1000,
		Season:               2024,
		PointsPerGame:        sql.NullFloat64{Float64: 28.0, Valid: true},
		YardsPerGame:         sql.NullFloat64{Float64: 420.0, Valid: true},
		PassYardsPerGame:     sql.NullFloat64{Float64: 240.0, Valid: true},
		RushYardsPerGame:     sql.NullFloat64{Float64: 180.0, Valid: true},
		YardsPerPlay:         sql.NullFloat64{Float64: 6.0, Valid: true},
		PointsAllowedPerGame: sql.NullFloat64{Float64: 21.0, Valid: true},
		YardsAllowedPerGame:  sql.NullFloat64{Float64: 350.0, Valid: true},
		Wins:                 sql.NullInt32{Int32: 7, Valid: true},
		Losses:               sql.NullInt32{Int32: 3, Valid: true},
	}

	err := db.Stats.Upsert(ctx, stats)
	require.NoError(t, err, "Should upsert season stats")

	// Retrieve and verify
	retrieved, err := db.Stats.GetByTeamAndSeason(ctx, 1000, 2024)
	require.NoError(t, err)
	assert.Equal(t, 28.0, retrieved.PointsPerGame.Float64)
	assert.Equal(t, 420.0, retrieved.YardsPerGame.Float64)
	assert.Equal(t, int32(7), retrieved.Wins.Int32)
	assert.Equal(t, int32(3), retrieved.Losses.Int32)

	// Update stats (simulate later in season)
	stats.PointsPerGame = sql.NullFloat64{Float64: 30.5, Valid: true}
	stats.Wins = sql.NullInt32{Int32: 8, Valid: true}
	stats.YardsPerGame = sql.NullFloat64{Float64: 435.0, Valid: true}

	err = db.Stats.Upsert(ctx, stats)
	require.NoError(t, err, "Should update season stats")

	// Verify update
	updated, err := db.Stats.GetByTeamAndSeason(ctx, 1000, 2024)
	require.NoError(t, err)
	assert.Equal(t, 30.5, updated.PointsPerGame.Float64)
	assert.Equal(t, int32(8), updated.Wins.Int32)
	assert.Equal(t, 435.0, updated.YardsPerGame.Float64)
}

func TestStatsRepository_GetByTeamAndSeason(t *testing.T) {
	db, ctx := setupTestDB(t)
	defer teardownTestDB(t, db)

	// Create test team
	team := &models.Team{TeamID: 1100, TeamCode: "GET", SchoolName: "Get Stats U"}
	require.NoError(t, db.Teams.Upsert(ctx, team))

	// Create stats for multiple seasons
	stats2023 := &models.TeamSeasonStats{
		TeamID:        1100,
		Season:        2023,
		PointsPerGame: sql.NullFloat64{Float64: 25.0, Valid: true},
		Wins:          sql.NullInt32{Int32: 9, Valid: true},
		Losses:        sql.NullInt32{Int32: 3, Valid: true},
	}
	stats2024 := &models.TeamSeasonStats{
		TeamID:        1100,
		Season:        2024,
		PointsPerGame: sql.NullFloat64{Float64: 28.0, Valid: true},
		Wins:          sql.NullInt32{Int32: 7, Valid: true},
		Losses:        sql.NullInt32{Int32: 3, Valid: true},
	}

	require.NoError(t, db.Stats.Upsert(ctx, stats2023))
	require.NoError(t, db.Stats.Upsert(ctx, stats2024))

	// Get 2024 stats
	retrieved2024, err := db.Stats.GetByTeamAndSeason(ctx, 1100, 2024)
	require.NoError(t, err)
	assert.Equal(t, 2024, retrieved2024.Season)
	assert.Equal(t, 28.0, retrieved2024.PointsPerGame.Float64)
	assert.Equal(t, int32(7), retrieved2024.Wins.Int32)

	// Get 2023 stats
	retrieved2023, err := db.Stats.GetByTeamAndSeason(ctx, 1100, 2023)
	require.NoError(t, err)
	assert.Equal(t, 2023, retrieved2023.Season)
	assert.Equal(t, 25.0, retrieved2023.PointsPerGame.Float64)
	assert.Equal(t, int32(9), retrieved2023.Wins.Int32)
}

func TestStatsRepository_CalculatedMetrics(t *testing.T) {
	db, ctx := setupTestDB(t)
	defer teardownTestDB(t, db)

	// Create test team
	team := &models.Team{TeamID: 1200, TeamCode: "CALC", SchoolName: "Calculate U"}
	require.NoError(t, db.Teams.Upsert(ctx, team))

	// Create stats with specific values for calculation testing
	stats := &models.TeamSeasonStats{
		TeamID:                 1200,
		Season:                 2024,
		PointsPerGame:          sql.NullFloat64{Float64: 30.0, Valid: true},
		YardsPerGame:           sql.NullFloat64{Float64: 420.0, Valid: true},
		PassYardsPerGame:       sql.NullFloat64{Float64: 245.0, Valid: true},
		RushYardsPerGame:       sql.NullFloat64{Float64: 175.0, Valid: true},
		YardsPerPlay:           sql.NullFloat64{Float64: 6.0, Valid: true},
		ThirdDownConversionPct: sql.NullFloat64{Float64: 0.45, Valid: true},
		RedZoneScoringPct:      sql.NullFloat64{Float64: 0.90, Valid: true},
		Wins:                   sql.NullInt32{Int32: 7, Valid: true},
		Losses:                 sql.NullInt32{Int32: 3, Valid: true},
	}

	require.NoError(t, db.Stats.Upsert(ctx, stats))

	// Retrieve and verify calculated metrics
	retrieved, err := db.Stats.GetByTeamAndSeason(ctx, 1200, 2024)
	require.NoError(t, err)

	// Verify values
	assert.Equal(t, 30.0, retrieved.PointsPerGame.Float64)
	assert.Equal(t, 420.0, retrieved.YardsPerGame.Float64)
	assert.Equal(t, 6.0, retrieved.YardsPerPlay.Float64)
	assert.Equal(t, 0.45, retrieved.ThirdDownConversionPct.Float64)
	assert.Equal(t, 0.90, retrieved.RedZoneScoringPct.Float64)
}

func TestStatsRepository_MultipleTeamStats(t *testing.T) {
	db, ctx := setupTestDB(t)
	defer teardownTestDB(t, db)

	// Create multiple teams
	teams := []struct {
		id   int
		code string
		name string
	}{
		{1400, "T1", "Team One"},
		{1401, "T2", "Team Two"},
		{1402, "T3", "Team Three"},
	}

	for _, tm := range teams {
		team := &models.Team{TeamID: tm.id, TeamCode: tm.code, SchoolName: tm.name}
		require.NoError(t, db.Teams.Upsert(ctx, team))

		// Create stats for each team with different values
		stats := &models.TeamSeasonStats{
			TeamID:        tm.id,
			Season:        2024,
			PointsPerGame: sql.NullFloat64{Float64: float64(20 + (tm.id % 10)), Valid: true},
			Wins:          sql.NullInt32{Int32: int32(tm.id % 10), Valid: true},
			Losses:        sql.NullInt32{Int32: int32(10 - (tm.id % 10)), Valid: true},
		}
		require.NoError(t, db.Stats.Upsert(ctx, stats))
	}

	// Verify each team has their own stats
	for _, tm := range teams {
		stats, err := db.Stats.GetByTeamAndSeason(ctx, tm.id, 2024)
		require.NoError(t, err)
		assert.Equal(t, tm.id, stats.TeamID)
		assert.Equal(t, int32(tm.id%10), stats.Wins.Int32)
	}
}

func TestStatsRepository_StatsNotFound(t *testing.T) {
	db, ctx := setupTestDB(t)
	defer teardownTestDB(t, db)

	// Try to get stats for non-existent team
	_, err := db.Stats.GetByTeamAndSeason(ctx, 99999, 2024)
	assert.Error(t, err, "Should return error for non-existent team stats")
}

func TestStatsRepository_ComprehensiveStats(t *testing.T) {
	db, ctx := setupTestDB(t)
	defer teardownTestDB(t, db)

	// Create test team
	team := &models.Team{TeamID: 1500, TeamCode: "COMP", SchoolName: "Comprehensive U"}
	require.NoError(t, db.Teams.Upsert(ctx, team))

	// Create stats with all possible fields
	stats := &models.TeamSeasonStats{
		TeamID: 1500,
		Season: 2024,
		// Offense
		PointsPerGame:    sql.NullFloat64{Float64: 30.0, Valid: true},
		YardsPerGame:     sql.NullFloat64{Float64: 420.0, Valid: true},
		PassYardsPerGame: sql.NullFloat64{Float64: 245.0, Valid: true},
		RushYardsPerGame: sql.NullFloat64{Float64: 175.0, Valid: true},
		YardsPerPlay:     sql.NullFloat64{Float64: 6.0, Valid: true},
		// Defense
		PointsAllowedPerGame:    sql.NullFloat64{Float64: 21.0, Valid: true},
		YardsAllowedPerGame:     sql.NullFloat64{Float64: 350.0, Valid: true},
		PassYardsAllowedPerGame: sql.NullFloat64{Float64: 200.0, Valid: true},
		RushYardsAllowedPerGame: sql.NullFloat64{Float64: 150.0, Valid: true},
		YardsPerPlayAllowed:     sql.NullFloat64{Float64: 5.0, Valid: true},
		// Efficiency
		ThirdDownConversionPct:  sql.NullFloat64{Float64: 0.45, Valid: true},
		FourthDownConversionPct: sql.NullFloat64{Float64: 0.50, Valid: true},
		RedZoneScoringPct:       sql.NullFloat64{Float64: 0.92, Valid: true},
		// Turnovers
		Turnovers:      sql.NullInt32{Int32: 15, Valid: true},
		Takeaways:      sql.NullInt32{Int32: 20, Valid: true},
		TurnoverMargin: sql.NullInt32{Int32: 5, Valid: true},
		// QB Stats
		QBRating:             sql.NullFloat64{Float64: 145.5, Valid: true},
		CompletionPercentage: sql.NullFloat64{Float64: 0.70, Valid: true},
		PassingTouchdowns:    sql.NullInt32{Int32: 27, Valid: true},
		Interceptions:        sql.NullInt32{Int32: 9, Valid: true},
		// Record
		Wins:   sql.NullInt32{Int32: 9, Valid: true},
		Losses: sql.NullInt32{Int32: 3, Valid: true},
	}

	require.NoError(t, db.Stats.Upsert(ctx, stats))

	// Retrieve and verify all fields
	retrieved, err := db.Stats.GetByTeamAndSeason(ctx, 1500, 2024)
	require.NoError(t, err)

	// Verify comprehensive stats
	assert.Equal(t, 30.0, retrieved.PointsPerGame.Float64)
	assert.Equal(t, 420.0, retrieved.YardsPerGame.Float64)
	assert.Equal(t, 245.0, retrieved.PassYardsPerGame.Float64)
	assert.Equal(t, 21.0, retrieved.PointsAllowedPerGame.Float64)
	assert.Equal(t, 0.45, retrieved.ThirdDownConversionPct.Float64)
	assert.Equal(t, 0.92, retrieved.RedZoneScoringPct.Float64)
	assert.Equal(t, int32(27), retrieved.PassingTouchdowns.Int32)
	assert.Equal(t, int32(9), retrieved.Wins.Int32)
}
