package repository

import (
	"database/sql"
	"testing"

	"ncaaf_v5/ingestion/internal/models"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestTeamRepository_Upsert(t *testing.T) {
	db, ctx := setupTestDB(t)
	defer teardownTestDB(t, db)

	team := &models.Team{
		TeamID:          1,
		TeamCode:        "ALA",
		SchoolName:      "Alabama",
		Mascot:          sql.NullString{String: "Crimson Tide", Valid: true},
		Conference:      sql.NullString{String: "SEC", Valid: true},
		Division:        sql.NullString{String: "FBS", Valid: true},
		TalentComposite: sql.NullFloat64{Float64: 95.5, Valid: true},
	}

	// Insert new team
	err := db.Teams.Upsert(ctx, team)
	require.NoError(t, err, "Should successfully insert team")

	// Verify team was created
	retrieved, err := db.Teams.GetByTeamID(ctx, team.TeamID)
	require.NoError(t, err, "Should retrieve inserted team")
	assert.Equal(t, team.TeamCode, retrieved.TeamCode, "Team codes should match")
	assert.Equal(t, team.SchoolName, retrieved.SchoolName, "School names should match")

	// Update existing team
	team.Mascot = sql.NullString{String: "Roll Tide", Valid: true}
	err = db.Teams.Upsert(ctx, team)
	require.NoError(t, err, "Should successfully update team")

	// Verify update
	updated, err := db.Teams.GetByTeamID(ctx, team.TeamID)
	require.NoError(t, err, "Should retrieve updated team")
	assert.Equal(t, "Roll Tide", updated.Mascot.String, "Mascot should be updated")
}

func TestTeamRepository_GetByCode(t *testing.T) {
	db, ctx := setupTestDB(t)
	defer teardownTestDB(t, db)

	team := &models.Team{
		TeamID:     2,
		TeamCode:   "CLEM",
		SchoolName: "Clemson",
		Conference: sql.NullString{String: "ACC", Valid: true},
	}

	err := db.Teams.Upsert(ctx, team)
	require.NoError(t, err, "Should insert team")

	// Get by code
	retrieved, err := db.Teams.GetByTeamCode(ctx, "CLEM")
	require.NoError(t, err, "Should retrieve team by code")
	assert.Equal(t, team.TeamID, retrieved.TeamID, "Team IDs should match")
	assert.Equal(t, "Clemson", retrieved.SchoolName, "School names should match")
}

func TestTeamRepository_List(t *testing.T) {
	db, ctx := setupTestDB(t)
	defer teardownTestDB(t, db)

	// Insert multiple teams
	teams := []*models.Team{
		{TeamID: 10, TeamCode: "OSU", SchoolName: "Ohio State", Conference: sql.NullString{String: "Big Ten", Valid: true}},
		{TeamID: 11, TeamCode: "MICH", SchoolName: "Michigan", Conference: sql.NullString{String: "Big Ten", Valid: true}},
		{TeamID: 12, TeamCode: "GA", SchoolName: "Georgia", Conference: sql.NullString{String: "SEC", Valid: true}},
	}

	for _, team := range teams {
		err := db.Teams.Upsert(ctx, team)
		require.NoError(t, err, "Should insert team")
	}

	// List all teams
	allTeams, err := db.Teams.List(ctx)
	require.NoError(t, err, "Should list teams")
	assert.GreaterOrEqual(t, len(allTeams), 3, "Should have at least 3 teams")
}

func TestTeamRepository_GetNotFound(t *testing.T) {
	db, ctx := setupTestDB(t)
	defer teardownTestDB(t, db)

	// Try to get non-existent team
	_, err := db.Teams.GetByTeamID(ctx, 99999)
	assert.Error(t, err, "Should return error for non-existent team")
}
