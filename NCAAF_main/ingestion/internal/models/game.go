package models

import (
	"database/sql"
	"time"
)

// Game represents a college football game
type Game struct {
	ID            int            `db:"id"`
	GameID        int            `db:"game_id"`
	Season        int            `db:"season"`
	Week          int            `db:"week"`
	HomeTeamID    int            `db:"home_team_id"`
	AwayTeamID    int            `db:"away_team_id"`
	HomeTeamCode  string         `db:"home_team_code"`
	AwayTeamCode  string         `db:"away_team_code"`
	GameDate      time.Time      `db:"game_date"`
	StadiumID     sql.NullInt32  `db:"stadium_id"`
	Status        string         `db:"status"`
	Period        sql.NullString `db:"period"`
	TimeRemaining sql.NullString `db:"time_remaining"`

	// Scores
	HomeScore sql.NullInt32 `db:"home_score"`
	AwayScore sql.NullInt32 `db:"away_score"`

	// Quarter scores
	HomeScoreQuarter1 sql.NullInt32 `db:"home_score_quarter_1"`
	HomeScoreQuarter2 sql.NullInt32 `db:"home_score_quarter_2"`
	HomeScoreQuarter3 sql.NullInt32 `db:"home_score_quarter_3"`
	HomeScoreQuarter4 sql.NullInt32 `db:"home_score_quarter_4"`
	HomeScoreOvertime sql.NullInt32 `db:"home_score_overtime"`

	AwayScoreQuarter1 sql.NullInt32 `db:"away_score_quarter_1"`
	AwayScoreQuarter2 sql.NullInt32 `db:"away_score_quarter_2"`
	AwayScoreQuarter3 sql.NullInt32 `db:"away_score_quarter_3"`
	AwayScoreQuarter4 sql.NullInt32 `db:"away_score_quarter_4"`
	AwayScoreOvertime sql.NullInt32 `db:"away_score_overtime"`

	// Derived fields (computed in DB)
	TotalScore sql.NullInt32 `db:"total_score"`
	Margin     sql.NullInt32 `db:"margin"`

	CreatedAt time.Time `db:"created_at"`
	UpdatedAt time.Time `db:"updated_at"`
}

// GameInput is used for creating/updating games from API
type GameInput struct {
	GameID        int    `json:"GameID"`
	Season        int    `json:"Season"`
	Week          int    `json:"Week"`
	HomeTeamID    int    `json:"HomeTeamID"`
	AwayTeamID    int    `json:"AwayTeamID"`
	HomeTeam      string `json:"HomeTeam"` // Team code
	AwayTeam      string `json:"AwayTeam"` // Team code
	DateTime      string `json:"DateTime"` // ISO 8601 format
	StadiumID     *int   `json:"StadiumID,omitempty"`
	Status        string `json:"Status"`
	Period        string `json:"Period"`
	TimeRemaining string `json:"TimeRemaining"`

	// Scores
	HomeScore *int `json:"HomeScore,omitempty"`
	AwayScore *int `json:"AwayScore,omitempty"`

	// Quarter scores
	HomeScoreQuarter1 *int `json:"HomeScoreQuarter1,omitempty"`
	HomeScoreQuarter2 *int `json:"HomeScoreQuarter2,omitempty"`
	HomeScoreQuarter3 *int `json:"HomeScoreQuarter3,omitempty"`
	HomeScoreQuarter4 *int `json:"HomeScoreQuarter4,omitempty"`
	HomeScoreOvertime *int `json:"HomeScoreOvertime,omitempty"`

	AwayScoreQuarter1 *int `json:"AwayScoreQuarter1,omitempty"`
	AwayScoreQuarter2 *int `json:"AwayScoreQuarter2,omitempty"`
	AwayScoreQuarter3 *int `json:"AwayScoreQuarter3,omitempty"`
	AwayScoreQuarter4 *int `json:"AwayScoreQuarter4,omitempty"`
	AwayScoreOvertime *int `json:"AwayScoreOvertime,omitempty"`
}

// ToGame converts GameInput (from API) to Game model
// Note: HomeTeamID and AwayTeamID need to be resolved from database
func (gi *GameInput) ToGame(homeTeamDBID, awayTeamDBID int) *Game {
	game := &Game{
		GameID:       gi.GameID,
		Season:       gi.Season,
		Week:         gi.Week,
		HomeTeamID:   homeTeamDBID,
		AwayTeamID:   awayTeamDBID,
		HomeTeamCode: gi.HomeTeam,
		AwayTeamCode: gi.AwayTeam,
		Status:       gi.Status,
	}

	// Parse game date
	if gameTime, err := time.Parse(time.RFC3339, gi.DateTime); err == nil {
		game.GameDate = gameTime
	}

	// Stadium
	if gi.StadiumID != nil && *gi.StadiumID > 0 {
		stadiumID := int32(*gi.StadiumID)
		game.StadiumID = sql.NullInt32{Int32: stadiumID, Valid: true}
	}

	// Period and time
	if gi.Period != "" {
		game.Period = sql.NullString{String: gi.Period, Valid: true}
	}
	if gi.TimeRemaining != "" {
		game.TimeRemaining = sql.NullString{String: gi.TimeRemaining, Valid: true}
	}

	// Scores
	if gi.HomeScore != nil {
		game.HomeScore = sql.NullInt32{Int32: int32(*gi.HomeScore), Valid: true}
	}
	if gi.AwayScore != nil {
		game.AwayScore = sql.NullInt32{Int32: int32(*gi.AwayScore), Valid: true}
	}

	// Quarter scores - Home
	if gi.HomeScoreQuarter1 != nil {
		game.HomeScoreQuarter1 = sql.NullInt32{Int32: int32(*gi.HomeScoreQuarter1), Valid: true}
	}
	if gi.HomeScoreQuarter2 != nil {
		game.HomeScoreQuarter2 = sql.NullInt32{Int32: int32(*gi.HomeScoreQuarter2), Valid: true}
	}
	if gi.HomeScoreQuarter3 != nil {
		game.HomeScoreQuarter3 = sql.NullInt32{Int32: int32(*gi.HomeScoreQuarter3), Valid: true}
	}
	if gi.HomeScoreQuarter4 != nil {
		game.HomeScoreQuarter4 = sql.NullInt32{Int32: int32(*gi.HomeScoreQuarter4), Valid: true}
	}
	if gi.HomeScoreOvertime != nil {
		game.HomeScoreOvertime = sql.NullInt32{Int32: int32(*gi.HomeScoreOvertime), Valid: true}
	}

	// Quarter scores - Away
	if gi.AwayScoreQuarter1 != nil {
		game.AwayScoreQuarter1 = sql.NullInt32{Int32: int32(*gi.AwayScoreQuarter1), Valid: true}
	}
	if gi.AwayScoreQuarter2 != nil {
		game.AwayScoreQuarter2 = sql.NullInt32{Int32: int32(*gi.AwayScoreQuarter2), Valid: true}
	}
	if gi.AwayScoreQuarter3 != nil {
		game.AwayScoreQuarter3 = sql.NullInt32{Int32: int32(*gi.AwayScoreQuarter3), Valid: true}
	}
	if gi.AwayScoreQuarter4 != nil {
		game.AwayScoreQuarter4 = sql.NullInt32{Int32: int32(*gi.AwayScoreQuarter4), Valid: true}
	}
	if gi.AwayScoreOvertime != nil {
		game.AwayScoreOvertime = sql.NullInt32{Int32: int32(*gi.AwayScoreOvertime), Valid: true}
	}

	return game
}

// IsActive returns true if the game is currently in progress
func (g *Game) IsActive() bool {
	return g.Status == "InProgress"
}

// IsScheduled returns true if the game is scheduled but not started
func (g *Game) IsScheduled() bool {
	return g.Status == "Scheduled"
}

// IsFinal returns true if the game is completed
func (g *Game) IsFinal() bool {
	return g.Status == "Final"
}
