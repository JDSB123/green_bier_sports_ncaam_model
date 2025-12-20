package repository

import (
	"database/sql"
	"testing"
	"time"

	"ncaaf_v5/ingestion/internal/models"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestGameRepository_Upsert(t *testing.T) {
	db, ctx := setupTestDB(t)
	defer teardownTestDB(t, db)

	// Create test teams first
	homeTeam := &models.Team{TeamID: 100, TeamCode: "HOME", SchoolName: "Home University"}
	awayTeam := &models.Team{TeamID: 101, TeamCode: "AWAY", SchoolName: "Away University"}

	require.NoError(t, db.Teams.Upsert(ctx, homeTeam))
	require.NoError(t, db.Teams.Upsert(ctx, awayTeam))

	game := &models.Game{
		GameID:     1000,
		Season:     2024,
		Week:       10,
		HomeTeamID: 100,
		AwayTeamID: 101,
		GameDate:   time.Now().Add(24 * time.Hour),
		Status:     "Scheduled",
		HomeScore:  sql.NullInt32{Valid: false},
		AwayScore:  sql.NullInt32{Valid: false},
	}

	// Insert game
	err := db.Games.Upsert(ctx, game)
	require.NoError(t, err, "Should insert game")

	// Retrieve and verify
	retrieved, err := db.Games.GetByGameID(ctx, 1000)
	require.NoError(t, err, "Should retrieve game")
	assert.Equal(t, game.Season, retrieved.Season)
	assert.Equal(t, game.HomeTeamID, retrieved.HomeTeamID)
	assert.Equal(t, "Scheduled", retrieved.Status)

	// Update game status and scores
	game.Status = "InProgress"
	game.HomeScore = sql.NullInt32{Int32: 21, Valid: true}
	game.AwayScore = sql.NullInt32{Int32: 14, Valid: true}

	err = db.Games.Upsert(ctx, game)
	require.NoError(t, err, "Should update game")

	// Verify update
	updated, err := db.Games.GetByGameID(ctx, 1000)
	require.NoError(t, err)
	assert.Equal(t, "InProgress", updated.Status)
	assert.Equal(t, int32(21), updated.HomeScore.Int32)
	assert.Equal(t, int32(14), updated.AwayScore.Int32)
	// Generated columns
	assert.Equal(t, int32(35), updated.TotalScore.Int32, "Total should be auto-calculated")
	assert.Equal(t, int32(7), updated.Margin.Int32, "Margin should be auto-calculated")
}

func TestGameRepository_GetActiveGames(t *testing.T) {
	db, ctx := setupTestDB(t)
	defer teardownTestDB(t, db)

	// Create test teams
	for i := 200; i < 210; i++ {
		team := &models.Team{
			TeamID:     i,
			TeamCode:   string(rune('A' + i - 200)),
			SchoolName: "Team " + string(rune('A'+i-200)),
		}
		require.NoError(t, db.Teams.Upsert(ctx, team))
	}

	// Create games with different statuses
	games := []*models.Game{
		{GameID: 2001, Season: 2024, Week: 10,
			HomeTeamID: 200, AwayTeamID: 201, Status: "InProgress",
			GameDate: time.Now()},
		{GameID: 2002, Season: 2024, Week: 10,
			HomeTeamID: 202, AwayTeamID: 203, Status: "InProgress",
			GameDate: time.Now()},
		{GameID: 2003, Season: 2024, Week: 10,
			HomeTeamID: 204, AwayTeamID: 205, Status: "Scheduled",
			GameDate: time.Now().Add(24 * time.Hour)},
		{GameID: 2004, Season: 2024, Week: 10,
			HomeTeamID: 206, AwayTeamID: 207, Status: "Final",
			GameDate: time.Now().Add(-24 * time.Hour)},
	}

	for _, game := range games {
		require.NoError(t, db.Games.Upsert(ctx, game))
	}

	// Get active games
	activeGames, err := db.Games.GetActiveGames(ctx)
	require.NoError(t, err, "Should retrieve active games")
	assert.Len(t, activeGames, 2, "Should have exactly 2 games in progress")

	// Verify all returned games are InProgress
	for _, game := range activeGames {
		assert.Equal(t, "InProgress", game.Status, "All active games should have InProgress status")
	}
}

func TestGameRepository_GetByWeek(t *testing.T) {
	db, ctx := setupTestDB(t)
	defer teardownTestDB(t, db)

	// Create teams
	team1 := &models.Team{TeamID: 300, TeamCode: "T1", SchoolName: "Team 1"}
	team2 := &models.Team{TeamID: 301, TeamCode: "T2", SchoolName: "Team 2"}
	require.NoError(t, db.Teams.Upsert(ctx, team1))
	require.NoError(t, db.Teams.Upsert(ctx, team2))

	// Create games in different weeks
	week12Game := &models.Game{
		GameID: 3001, Season: 2024, Week: 12,
		HomeTeamID: 300, AwayTeamID: 301, Status: "Scheduled",
		GameDate: time.Now(),
	}
	week13Game := &models.Game{
		GameID: 3002, Season: 2024, Week: 13,
		HomeTeamID: 300, AwayTeamID: 301, Status: "Scheduled",
		GameDate: time.Now(),
	}

	require.NoError(t, db.Games.Upsert(ctx, week12Game))
	require.NoError(t, db.Games.Upsert(ctx, week13Game))

	// Get games for week 12
	week12Games, err := db.Games.GetByWeek(ctx, 2024, 12)
	require.NoError(t, err)
	assert.GreaterOrEqual(t, len(week12Games), 1, "Should have at least 1 game in week 12")

	// Verify all games are from week 12
	for _, game := range week12Games {
		assert.Equal(t, 12, game.Week, "All games should be from week 12")
		assert.Equal(t, 2024, game.Season, "All games should be from 2024 season")
	}
}

func TestGameRepository_Update(t *testing.T) {
	db, ctx := setupTestDB(t)
	defer teardownTestDB(t, db)

	// Create teams
	homeTeam := &models.Team{TeamID: 400, TeamCode: "HT", SchoolName: "Home Team"}
	awayTeam := &models.Team{TeamID: 401, TeamCode: "AT", SchoolName: "Away Team"}
	require.NoError(t, db.Teams.Upsert(ctx, homeTeam))
	require.NoError(t, db.Teams.Upsert(ctx, awayTeam))

	// Create game
	game := &models.Game{
		GameID: 4001, Season: 2024, Week: 10,
		HomeTeamID: 400, AwayTeamID: 401, Status: "InProgress",
		GameDate:  time.Now(),
		HomeScore: sql.NullInt32{Int32: 0, Valid: true},
		AwayScore: sql.NullInt32{Int32: 0, Valid: true},
		Period:    sql.NullString{String: "1st", Valid: true},
	}
	require.NoError(t, db.Games.Upsert(ctx, game))

	// Update scores during game
	game.HomeScore = sql.NullInt32{Int32: 7, Valid: true}
	game.Period = sql.NullString{String: "2nd", Valid: true}
	err := db.Games.Upsert(ctx, game)
	require.NoError(t, err, "Should update game")

	// Verify update
	updated, err := db.Games.GetByGameID(ctx, 4001)
	require.NoError(t, err)
	assert.Equal(t, int32(7), updated.HomeScore.Int32)
	assert.Equal(t, "2nd", updated.Period.String)
}
