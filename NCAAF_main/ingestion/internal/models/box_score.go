package models

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"time"
)

// BoxScore represents detailed game statistics for a team
type BoxScore struct {
	ID     int `db:"id"`
	GameID int `db:"game_id"`
	TeamID int `db:"team_id"`

	// Basic stats
	Points        sql.NullInt32 `db:"points"`
	FirstDowns    sql.NullInt32 `db:"first_downs"`
	TotalYards    sql.NullInt32 `db:"total_yards"`
	PassingYards  sql.NullInt32 `db:"passing_yards"`
	RushingYards  sql.NullInt32 `db:"rushing_yards"`
	Penalties     sql.NullInt32 `db:"penalties"`
	PenaltyYards  sql.NullInt32 `db:"penalty_yards"`
	Turnovers     sql.NullInt32 `db:"turnovers"`
	FumblesLost   sql.NullInt32 `db:"fumbles_lost"`
	Interceptions sql.NullInt32 `db:"interceptions"`

	// Possession
	PossessionMinutes sql.NullInt32 `db:"possession_minutes"`
	PossessionSeconds sql.NullInt32 `db:"possession_seconds"`

	// Efficiency
	ThirdDownAttempts     sql.NullInt32 `db:"third_down_attempts"`
	ThirdDownConversions  sql.NullInt32 `db:"third_down_conversions"`
	FourthDownAttempts    sql.NullInt32 `db:"fourth_down_attempts"`
	FourthDownConversions sql.NullInt32 `db:"fourth_down_conversions"`
	RedZoneAttempts       sql.NullInt32 `db:"red_zone_attempts"`
	RedZoneConversions    sql.NullInt32 `db:"red_zone_conversions"`

	// Quarter breakdown (JSONB)
	QuarterScores json.RawMessage `db:"quarter_scores"`

	CreatedAt time.Time `db:"created_at"`
	UpdatedAt time.Time `db:"updated_at"`
}

// QuarterScores represents the JSONB structure for quarter breakdown
type QuarterScores struct {
	Q1 int `json:"Q1"`
	Q2 int `json:"Q2"`
	Q3 int `json:"Q3"`
	Q4 int `json:"Q4"`
	OT int `json:"OT,omitempty"`
}

// BoxScoreInput is used for creating/updating box scores from API
type BoxScoreInput struct {
	GameID int `json:"GameID"`
	TeamID int `json:"TeamID"`

	// Basic stats
	Points        *int `json:"Points,omitempty"`
	FirstDowns    *int `json:"FirstDowns,omitempty"`
	TotalYards    *int `json:"TotalOffensiveYards,omitempty"`
	PassingYards  *int `json:"PassingYards,omitempty"`
	RushingYards  *int `json:"RushingYards,omitempty"`
	Penalties     *int `json:"Penalties,omitempty"`
	PenaltyYards  *int `json:"PenaltyYards,omitempty"`
	Turnovers     *int `json:"Turnovers,omitempty"`
	FumblesLost   *int `json:"FumblesLost,omitempty"`
	Interceptions *int `json:"InterceptionsThrownInt,omitempty"`

	// Possession
	TimeOfPossession string `json:"TimeOfPossession"` // Format: "MM:SS"

	// Efficiency
	ThirdDownAttempts     *int `json:"ThirdDownAttempts,omitempty"`
	ThirdDownConversions  *int `json:"ThirdDownConversions,omitempty"`
	FourthDownAttempts    *int `json:"FourthDownAttempts,omitempty"`
	FourthDownConversions *int `json:"FourthDownConversions,omitempty"`
	RedZoneAttempts       *int `json:"RedZoneAttempts,omitempty"`
	RedZoneConversions    *int `json:"RedZoneConversions,omitempty"`

	// Quarter scores
	ScoreQuarter1 *int `json:"ScoreQuarter1,omitempty"`
	ScoreQuarter2 *int `json:"ScoreQuarter2,omitempty"`
	ScoreQuarter3 *int `json:"ScoreQuarter3,omitempty"`
	ScoreQuarter4 *int `json:"ScoreQuarter4,omitempty"`
	ScoreOvertime *int `json:"ScoreOvertime,omitempty"`
}

// ToBoxScore converts BoxScoreInput (from API) to BoxScore model
func (bsi *BoxScoreInput) ToBoxScore(dbGameID, dbTeamID int) *BoxScore {
	boxScore := &BoxScore{
		GameID: dbGameID,
		TeamID: dbTeamID,
	}

	// Basic stats
	if bsi.Points != nil {
		boxScore.Points = sql.NullInt32{Int32: int32(*bsi.Points), Valid: true}
	}
	if bsi.FirstDowns != nil {
		boxScore.FirstDowns = sql.NullInt32{Int32: int32(*bsi.FirstDowns), Valid: true}
	}
	if bsi.TotalYards != nil {
		boxScore.TotalYards = sql.NullInt32{Int32: int32(*bsi.TotalYards), Valid: true}
	}
	if bsi.PassingYards != nil {
		boxScore.PassingYards = sql.NullInt32{Int32: int32(*bsi.PassingYards), Valid: true}
	}
	if bsi.RushingYards != nil {
		boxScore.RushingYards = sql.NullInt32{Int32: int32(*bsi.RushingYards), Valid: true}
	}
	if bsi.Penalties != nil {
		boxScore.Penalties = sql.NullInt32{Int32: int32(*bsi.Penalties), Valid: true}
	}
	if bsi.PenaltyYards != nil {
		boxScore.PenaltyYards = sql.NullInt32{Int32: int32(*bsi.PenaltyYards), Valid: true}
	}
	if bsi.Turnovers != nil {
		boxScore.Turnovers = sql.NullInt32{Int32: int32(*bsi.Turnovers), Valid: true}
	}
	if bsi.FumblesLost != nil {
		boxScore.FumblesLost = sql.NullInt32{Int32: int32(*bsi.FumblesLost), Valid: true}
	}
	if bsi.Interceptions != nil {
		boxScore.Interceptions = sql.NullInt32{Int32: int32(*bsi.Interceptions), Valid: true}
	}

	// Parse time of possession (format: "MM:SS")
	if bsi.TimeOfPossession != "" {
		var minutes, seconds int
		if _, err := time.ParseDuration(bsi.TimeOfPossession); err == nil {
			// Try parsing as MM:SS format
			if n, _ := fmt.Sscanf(bsi.TimeOfPossession, "%d:%d", &minutes, &seconds); n == 2 {
				boxScore.PossessionMinutes = sql.NullInt32{Int32: int32(minutes), Valid: true}
				boxScore.PossessionSeconds = sql.NullInt32{Int32: int32(seconds), Valid: true}
			}
		}
	}

	// Efficiency
	if bsi.ThirdDownAttempts != nil {
		boxScore.ThirdDownAttempts = sql.NullInt32{Int32: int32(*bsi.ThirdDownAttempts), Valid: true}
	}
	if bsi.ThirdDownConversions != nil {
		boxScore.ThirdDownConversions = sql.NullInt32{Int32: int32(*bsi.ThirdDownConversions), Valid: true}
	}
	if bsi.FourthDownAttempts != nil {
		boxScore.FourthDownAttempts = sql.NullInt32{Int32: int32(*bsi.FourthDownAttempts), Valid: true}
	}
	if bsi.FourthDownConversions != nil {
		boxScore.FourthDownConversions = sql.NullInt32{Int32: int32(*bsi.FourthDownConversions), Valid: true}
	}
	if bsi.RedZoneAttempts != nil {
		boxScore.RedZoneAttempts = sql.NullInt32{Int32: int32(*bsi.RedZoneAttempts), Valid: true}
	}
	if bsi.RedZoneConversions != nil {
		boxScore.RedZoneConversions = sql.NullInt32{Int32: int32(*bsi.RedZoneConversions), Valid: true}
	}

	// Quarter scores - build JSONB
	quarterScores := QuarterScores{}
	if bsi.ScoreQuarter1 != nil {
		quarterScores.Q1 = *bsi.ScoreQuarter1
	}
	if bsi.ScoreQuarter2 != nil {
		quarterScores.Q2 = *bsi.ScoreQuarter2
	}
	if bsi.ScoreQuarter3 != nil {
		quarterScores.Q3 = *bsi.ScoreQuarter3
	}
	if bsi.ScoreQuarter4 != nil {
		quarterScores.Q4 = *bsi.ScoreQuarter4
	}
	if bsi.ScoreOvertime != nil && *bsi.ScoreOvertime > 0 {
		quarterScores.OT = *bsi.ScoreOvertime
	}

	if jsonData, err := json.Marshal(quarterScores); err == nil {
		boxScore.QuarterScores = jsonData
	}

	return boxScore
}
