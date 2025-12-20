package repository

import (
	"database/sql"
	"testing"
	"time"

	"ncaaf_v5/ingestion/internal/models"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestOddsRepository_CreateOdds(t *testing.T) {
	db, ctx := setupTestDB(t)
	defer teardownTestDB(t, db)

	// Create test teams and game first
	homeTeam := &models.Team{TeamID: 500, TeamCode: "TESTH", SchoolName: "Test Home"}
	awayTeam := &models.Team{TeamID: 501, TeamCode: "TESTA", SchoolName: "Test Away"}
	require.NoError(t, db.Teams.Upsert(ctx, homeTeam))
	require.NoError(t, db.Teams.Upsert(ctx, awayTeam))

	game := &models.Game{
		GameID:     5001,
		Season:     2024,
		Week:       10,
		HomeTeamID: 500,
		AwayTeamID: 501,
		Status:     "Scheduled",
		GameDate:   time.Now().Add(24 * time.Hour),
	}
	require.NoError(t, db.Games.Upsert(ctx, game))

	// Create odds
	odds := &models.Odds{
		GameID:        5001,
		SportsbookID:  "1105", // Pinnacle
		HomeSpread:    sql.NullFloat64{Float64: -7.5, Valid: true},
		AwaySpread:    sql.NullFloat64{Float64: 7.5, Valid: true},
		OverUnder:     sql.NullFloat64{Float64: 52.5, Valid: true},
		HomeMoneyline: sql.NullInt32{Int32: -280, Valid: true},
		AwayMoneyline: sql.NullInt32{Int32: 240, Valid: true},
	}

	err := db.Odds.CreateOdds(ctx, odds)
	require.NoError(t, err, "Should create odds")

	// Verify odds was created
	retrieved, err := db.Odds.GetLatestOdds(ctx, 5001, "1105", "pregame", "Full Game")
	require.NoError(t, err, "Should retrieve created odds")
	assert.Equal(t, odds.GameID, retrieved.GameID)
	assert.Equal(t, odds.SportsbookID, retrieved.SportsbookID)
	assert.Equal(t, -7.5, retrieved.HomeSpread.Float64)
	assert.Equal(t, 52.5, retrieved.OverUnder.Float64)
}

func TestOddsRepository_GetLatestOdds(t *testing.T) {
	db, ctx := setupTestDB(t)
	defer teardownTestDB(t, db)

	// Setup teams and game
	homeTeam := &models.Team{TeamID: 600, TeamCode: "HT", SchoolName: "Home Team"}
	awayTeam := &models.Team{TeamID: 601, TeamCode: "AT", SchoolName: "Away Team"}
	require.NoError(t, db.Teams.Upsert(ctx, homeTeam))
	require.NoError(t, db.Teams.Upsert(ctx, awayTeam))

	game := &models.Game{
		GameID: 6001, Season: 2024, Week: 10,
		HomeTeamID: 600, AwayTeamID: 601, Status: "Scheduled",
		GameDate: time.Now().Add(24 * time.Hour),
	}
	require.NoError(t, db.Games.Upsert(ctx, game))

	// Create multiple odds for same game and sportsbook
	odds1 := &models.Odds{
		GameID: 6001, SportsbookID: "1105",
		HomeSpread: sql.NullFloat64{Float64: -7.0, Valid: true},
		OverUnder:  sql.NullFloat64{Float64: 50.0, Valid: true},
	}
	require.NoError(t, db.Odds.CreateOdds(ctx, odds1))

	time.Sleep(100 * time.Millisecond) // Ensure different timestamp

	odds2 := &models.Odds{
		GameID: 6001, SportsbookID: "1105",
		HomeSpread: sql.NullFloat64{Float64: -7.5, Valid: true},
		OverUnder:  sql.NullFloat64{Float64: 51.0, Valid: true},
	}
	require.NoError(t, db.Odds.CreateOdds(ctx, odds2))

	// Get latest odds - should return odds2
	latest, err := db.Odds.GetLatestOdds(ctx, 6001, "1105", "pregame", "Full Game")
	require.NoError(t, err)
	assert.Equal(t, -7.5, latest.HomeSpread.Float64, "Should return most recent odds")
	assert.Equal(t, 51.0, latest.OverUnder.Float64)
}

func TestOddsRepository_GetConsensusSpread(t *testing.T) {
	db, ctx := setupTestDB(t)
	defer teardownTestDB(t, db)

	// Setup teams and game
	homeTeam := &models.Team{TeamID: 700, TeamCode: "H7", SchoolName: "Home 7"}
	awayTeam := &models.Team{TeamID: 701, TeamCode: "A7", SchoolName: "Away 7"}
	require.NoError(t, db.Teams.Upsert(ctx, homeTeam))
	require.NoError(t, db.Teams.Upsert(ctx, awayTeam))

	game := &models.Game{
		GameID: 7001, Season: 2024, Week: 10,
		HomeTeamID: 700, AwayTeamID: 701, Status: "Scheduled",
		GameDate: time.Now().Add(24 * time.Hour),
	}
	require.NoError(t, db.Games.Upsert(ctx, game))

	// Create odds from multiple sharp sportsbooks
	sportsbooks := []struct {
		id     string
		spread float64
	}{
		{"1105", -7.0}, // Pinnacle
		{"1004", -7.5}, // Circa
		{"1002", -6.5}, // Consensus should be average: -7.0
	}

	for _, book := range sportsbooks {
		odds := &models.Odds{
			GameID:       7001,
			SportsbookID: book.id,
			HomeSpread:   sql.NullFloat64{Float64: book.spread, Valid: true},
			AwaySpread:   sql.NullFloat64{Float64: -book.spread, Valid: true},
		}
		require.NoError(t, db.Odds.CreateOdds(ctx, odds))
	}

	// Get consensus
	consensus, err := db.Odds.GetConsensusSpread(ctx, 7001, []string{"1105", "1004", "1002"})
	require.NoError(t, err)
	assert.InDelta(t, -7.0, consensus, 0.1, "Consensus should be average of sharp books")
}

func TestOddsRepository_LineMovement(t *testing.T) {
	db, ctx := setupTestDB(t)
	defer teardownTestDB(t, db)

	// Setup teams and game
	homeTeam := &models.Team{TeamID: 800, TeamCode: "H8", SchoolName: "Home 8"}
	awayTeam := &models.Team{TeamID: 801, TeamCode: "A8", SchoolName: "Away 8"}
	require.NoError(t, db.Teams.Upsert(ctx, homeTeam))
	require.NoError(t, db.Teams.Upsert(ctx, awayTeam))

	game := &models.Game{
		GameID: 8001, Season: 2024, Week: 10,
		HomeTeamID: 800, AwayTeamID: 801, Status: "Scheduled",
		GameDate: time.Now().Add(24 * time.Hour),
	}
	require.NoError(t, db.Games.Upsert(ctx, game))

	// Create initial odds
	initialOdds := &models.Odds{
		GameID: 8001, SportsbookID: "1105",
		HomeSpread: sql.NullFloat64{Float64: -7.0, Valid: true},
		AwaySpread: sql.NullFloat64{Float64: 7.0, Valid: true},
		OverUnder:  sql.NullFloat64{Float64: 50.0, Valid: true},
	}
	require.NoError(t, db.Odds.CreateOdds(ctx, initialOdds))

	// Create updated odds (line movement)
	updatedOdds := &models.Odds{
		GameID: 8001, SportsbookID: "1105",
		HomeSpread: sql.NullFloat64{Float64: -7.5, Valid: true},
		AwaySpread: sql.NullFloat64{Float64: 7.5, Valid: true},
		OverUnder:  sql.NullFloat64{Float64: 51.5, Valid: true},
	}

	// Track line movement
	err := db.Odds.TrackAndSaveOdds(ctx, updatedOdds)
	require.NoError(t, err, "Should track and save odds with line movement")

	// Verify line movement was recorded
	movements, err := db.Odds.GetLineMovementHistory(ctx, 8001, "1105", "pregame")
	require.NoError(t, err)
	assert.GreaterOrEqual(t, len(movements), 1, "Should have at least one line movement")

	if len(movements) > 0 {
		movement := movements[0]
		assert.Equal(t, 8001, movement.GameID)
		assert.Equal(t, "1105", movement.SportsbookID)
		// Verify spread moved
		if movement.PrevHomeSpread.Valid {
			assert.Equal(t, -7.0, movement.PrevHomeSpread.Float64)
		}
		if movement.NewHomeSpread.Valid {
			assert.Equal(t, -7.5, movement.NewHomeSpread.Float64)
		}
	}
}

func TestOddsRepository_GetOddsByGame(t *testing.T) {
	db, ctx := setupTestDB(t)
	defer teardownTestDB(t, db)

	// Setup teams and game
	homeTeam := &models.Team{TeamID: 900, TeamCode: "H9", SchoolName: "Home 9"}
	awayTeam := &models.Team{TeamID: 901, TeamCode: "A9", SchoolName: "Away 9"}
	require.NoError(t, db.Teams.Upsert(ctx, homeTeam))
	require.NoError(t, db.Teams.Upsert(ctx, awayTeam))

	game := &models.Game{
		GameID: 9001, Season: 2024, Week: 10,
		HomeTeamID: 900, AwayTeamID: 901, Status: "Scheduled",
		GameDate: time.Now().Add(24 * time.Hour),
	}
	require.NoError(t, db.Games.Upsert(ctx, game))

	// Create odds from multiple sportsbooks
	sportsbooks := []string{"1105", "1004", "1002"}
	for _, bookID := range sportsbooks {
		odds := &models.Odds{
			GameID:       9001,
			SportsbookID: bookID,
			HomeSpread:   sql.NullFloat64{Float64: -7.0, Valid: true},
		}
		require.NoError(t, db.Odds.CreateOdds(ctx, odds))
	}

	// Get all odds for game
	allOdds, err := db.Odds.GetAllOddsForGame(ctx, 9001)
	require.NoError(t, err)
	assert.GreaterOrEqual(t, len(allOdds), 3, "Should have odds from all sportsbooks")

	// Verify all sportsbooks present
	foundBooks := make(map[string]bool)
	for _, odds := range allOdds {
		foundBooks[odds.SportsbookID] = true
	}
	for _, bookID := range sportsbooks {
		assert.True(t, foundBooks[bookID], "Should have odds from "+bookID)
	}
}
