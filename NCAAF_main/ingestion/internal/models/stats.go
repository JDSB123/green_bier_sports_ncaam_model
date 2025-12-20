package models

import (
	"database/sql"
	"time"
)

// TeamSeasonStats represents season-level statistics for a team
type TeamSeasonStats struct {
	ID     int `db:"id"`
	TeamID int `db:"team_id"`
	Season int `db:"season"`

	// Offense
	PointsPerGame    sql.NullFloat64 `db:"points_per_game"`
	YardsPerGame     sql.NullFloat64 `db:"yards_per_game"`
	PassYardsPerGame sql.NullFloat64 `db:"pass_yards_per_game"`
	RushYardsPerGame sql.NullFloat64 `db:"rush_yards_per_game"`
	YardsPerPlay     sql.NullFloat64 `db:"yards_per_play"`

	// Defense
	PointsAllowedPerGame    sql.NullFloat64 `db:"points_allowed_per_game"`
	YardsAllowedPerGame     sql.NullFloat64 `db:"yards_allowed_per_game"`
	PassYardsAllowedPerGame sql.NullFloat64 `db:"pass_yards_allowed_per_game"`
	RushYardsAllowedPerGame sql.NullFloat64 `db:"rush_yards_allowed_per_game"`
	YardsPerPlayAllowed     sql.NullFloat64 `db:"yards_per_play_allowed"`

	// Efficiency
	ThirdDownConversionPct  sql.NullFloat64 `db:"third_down_conversion_pct"`
	FourthDownConversionPct sql.NullFloat64 `db:"fourth_down_conversion_pct"`
	RedZoneScoringPct       sql.NullFloat64 `db:"red_zone_scoring_pct"`

	// Turnovers
	Turnovers      sql.NullInt32 `db:"turnovers"`
	Takeaways      sql.NullInt32 `db:"takeaways"`
	TurnoverMargin sql.NullInt32 `db:"turnover_margin"`

	// Special Teams
	PuntReturnYardsPerAttempt sql.NullFloat64 `db:"punt_return_yards_per_attempt"`
	KickReturnYardsPerAttempt sql.NullFloat64 `db:"kick_return_yards_per_attempt"`

	// QB Stats (aggregated)
	QBRating             sql.NullFloat64 `db:"qb_rating"`
	CompletionPercentage sql.NullFloat64 `db:"completion_percentage"`
	PassingTouchdowns    sql.NullInt32   `db:"passing_touchdowns"`
	Interceptions        sql.NullInt32   `db:"interceptions"`

	// Record
	Wins   sql.NullInt32 `db:"wins"`
	Losses sql.NullInt32 `db:"losses"`

	CreatedAt time.Time `db:"created_at"`
	UpdatedAt time.Time `db:"updated_at"`
}

// TeamSeasonStatsInput is used for creating/updating stats from API
type TeamSeasonStatsInput struct {
	TeamID int `json:"TeamID"`
	Season int `json:"Season"`

	// Offense
	PointsPerGame    *float64 `json:"PointsPerGame,omitempty"`
	YardsPerGame     *float64 `json:"TotalYardsPerGame,omitempty"`
	PassYardsPerGame *float64 `json:"PassingYardsPerGame,omitempty"`
	RushYardsPerGame *float64 `json:"RushingYardsPerGame,omitempty"`
	YardsPerPlay     *float64 `json:"YardsPerPlay,omitempty"`

	// Defense
	PointsAllowedPerGame    *float64 `json:"PointsAllowedPerGame,omitempty"`
	YardsAllowedPerGame     *float64 `json:"YardsAllowedPerGame,omitempty"`
	PassYardsAllowedPerGame *float64 `json:"PassingYardsAllowedPerGame,omitempty"`
	RushYardsAllowedPerGame *float64 `json:"RushingYardsAllowedPerGame,omitempty"`
	YardsPerPlayAllowed     *float64 `json:"YardsPerPlayAllowed,omitempty"`

	// Efficiency
	ThirdDownConversionPct  *float64 `json:"ThirdDownConversionPercentage,omitempty"`
	FourthDownConversionPct *float64 `json:"FourthDownConversionPercentage,omitempty"`
	RedZoneScoringPct       *float64 `json:"RedZoneScoringPercentage,omitempty"`

	// Turnovers
	Turnovers      *int `json:"Turnovers,omitempty"`
	Takeaways      *int `json:"Takeaways,omitempty"`
	TurnoverMargin *int `json:"TurnoverMargin,omitempty"`

	// Special Teams
	PuntReturnYardsPerAttempt *float64 `json:"PuntReturnAverage,omitempty"`
	KickReturnYardsPerAttempt *float64 `json:"KickReturnAverage,omitempty"`

	// QB Stats
	QBRating             *float64 `json:"PasserRating,omitempty"`
	CompletionPercentage *float64 `json:"CompletionPercentage,omitempty"`
	PassingTouchdowns    *int     `json:"PassingTouchdowns,omitempty"`
	Interceptions        *int     `json:"Interceptions,omitempty"`

	// Record
	Wins   *int `json:"Wins,omitempty"`
	Losses *int `json:"Losses,omitempty"`
}

// ToTeamSeasonStats converts TeamSeasonStatsInput (from API) to TeamSeasonStats model
func (tsi *TeamSeasonStatsInput) ToTeamSeasonStats(dbTeamID int) *TeamSeasonStats {
	stats := &TeamSeasonStats{
		TeamID: dbTeamID,
		Season: tsi.Season,
	}

	// Offense
	if tsi.PointsPerGame != nil {
		stats.PointsPerGame = sql.NullFloat64{Float64: *tsi.PointsPerGame, Valid: true}
	}
	if tsi.YardsPerGame != nil {
		stats.YardsPerGame = sql.NullFloat64{Float64: *tsi.YardsPerGame, Valid: true}
	}
	if tsi.PassYardsPerGame != nil {
		stats.PassYardsPerGame = sql.NullFloat64{Float64: *tsi.PassYardsPerGame, Valid: true}
	}
	if tsi.RushYardsPerGame != nil {
		stats.RushYardsPerGame = sql.NullFloat64{Float64: *tsi.RushYardsPerGame, Valid: true}
	}
	if tsi.YardsPerPlay != nil {
		stats.YardsPerPlay = sql.NullFloat64{Float64: *tsi.YardsPerPlay, Valid: true}
	}

	// Defense
	if tsi.PointsAllowedPerGame != nil {
		stats.PointsAllowedPerGame = sql.NullFloat64{Float64: *tsi.PointsAllowedPerGame, Valid: true}
	}
	if tsi.YardsAllowedPerGame != nil {
		stats.YardsAllowedPerGame = sql.NullFloat64{Float64: *tsi.YardsAllowedPerGame, Valid: true}
	}
	if tsi.PassYardsAllowedPerGame != nil {
		stats.PassYardsAllowedPerGame = sql.NullFloat64{Float64: *tsi.PassYardsAllowedPerGame, Valid: true}
	}
	if tsi.RushYardsAllowedPerGame != nil {
		stats.RushYardsAllowedPerGame = sql.NullFloat64{Float64: *tsi.RushYardsAllowedPerGame, Valid: true}
	}
	if tsi.YardsPerPlayAllowed != nil {
		stats.YardsPerPlayAllowed = sql.NullFloat64{Float64: *tsi.YardsPerPlayAllowed, Valid: true}
	}

	// Efficiency
	if tsi.ThirdDownConversionPct != nil {
		stats.ThirdDownConversionPct = sql.NullFloat64{Float64: *tsi.ThirdDownConversionPct, Valid: true}
	}
	if tsi.FourthDownConversionPct != nil {
		stats.FourthDownConversionPct = sql.NullFloat64{Float64: *tsi.FourthDownConversionPct, Valid: true}
	}
	if tsi.RedZoneScoringPct != nil {
		stats.RedZoneScoringPct = sql.NullFloat64{Float64: *tsi.RedZoneScoringPct, Valid: true}
	}

	// Turnovers
	if tsi.Turnovers != nil {
		stats.Turnovers = sql.NullInt32{Int32: int32(*tsi.Turnovers), Valid: true}
	}
	if tsi.Takeaways != nil {
		stats.Takeaways = sql.NullInt32{Int32: int32(*tsi.Takeaways), Valid: true}
	}
	if tsi.TurnoverMargin != nil {
		stats.TurnoverMargin = sql.NullInt32{Int32: int32(*tsi.TurnoverMargin), Valid: true}
	}

	// Special Teams
	if tsi.PuntReturnYardsPerAttempt != nil {
		stats.PuntReturnYardsPerAttempt = sql.NullFloat64{Float64: *tsi.PuntReturnYardsPerAttempt, Valid: true}
	}
	if tsi.KickReturnYardsPerAttempt != nil {
		stats.KickReturnYardsPerAttempt = sql.NullFloat64{Float64: *tsi.KickReturnYardsPerAttempt, Valid: true}
	}

	// QB Stats
	if tsi.QBRating != nil {
		stats.QBRating = sql.NullFloat64{Float64: *tsi.QBRating, Valid: true}
	}
	if tsi.CompletionPercentage != nil {
		stats.CompletionPercentage = sql.NullFloat64{Float64: *tsi.CompletionPercentage, Valid: true}
	}
	if tsi.PassingTouchdowns != nil {
		stats.PassingTouchdowns = sql.NullInt32{Int32: int32(*tsi.PassingTouchdowns), Valid: true}
	}
	if tsi.Interceptions != nil {
		stats.Interceptions = sql.NullInt32{Int32: int32(*tsi.Interceptions), Valid: true}
	}

	// Record
	if tsi.Wins != nil {
		stats.Wins = sql.NullInt32{Int32: int32(*tsi.Wins), Valid: true}
	}
	if tsi.Losses != nil {
		stats.Losses = sql.NullInt32{Int32: int32(*tsi.Losses), Valid: true}
	}

	return stats
}
