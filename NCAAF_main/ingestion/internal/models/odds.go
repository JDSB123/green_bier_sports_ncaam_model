package models

import (
	"database/sql"
	"strconv"
	"time"
)

// Odds represents betting odds for a game from a specific sportsbook
type Odds struct {
	ID             int            `db:"id"`
	GameID         int            `db:"game_id"`
	SportsbookID   string         `db:"sportsbook_id"`
	SportsbookName sql.NullString `db:"sportsbook_name"`
	MarketType     string         `db:"market_type"`
	Period         string         `db:"period"`

	// Line values
	HomeSpread    sql.NullFloat64 `db:"home_spread"`
	AwaySpread    sql.NullFloat64 `db:"away_spread"`
	OverUnder     sql.NullFloat64 `db:"over_under"`
	HomeMoneyline sql.NullInt32   `db:"home_moneyline"`
	AwayMoneyline sql.NullInt32   `db:"away_moneyline"`
	HomeTeamTotal sql.NullFloat64 `db:"home_team_total"`
	AwayTeamTotal sql.NullFloat64 `db:"away_team_total"`

	// Juice (vig)
	HomeSpreadJuice sql.NullInt32 `db:"home_spread_juice"`
	AwaySpreadJuice sql.NullInt32 `db:"away_spread_juice"`
	OverJuice       sql.NullInt32 `db:"over_juice"`
	UnderJuice      sql.NullInt32 `db:"under_juice"`

	FetchedAt time.Time `db:"fetched_at"`
	CreatedAt time.Time `db:"created_at"`
	UpdatedAt time.Time `db:"updated_at"`
}

// OddsInput is used for creating/updating odds from API
type OddsInput struct {
	GameOddID      int    `json:"GameOddId"`
	GameID         int    `json:"GameId"`
	SportsbookID   int    `json:"SportsbookId"`
	SportsbookName string `json:"Sportsbook"`
	OddsType       string `json:"OddType"`

	// Spread
	HomeSpread       *float64 `json:"HomePointSpread"`
	AwaySpread       *float64 `json:"AwayPointSpread"`
	HomeSpreadPayout *int     `json:"HomePointSpreadPayout"`
	AwaySpreadPayout *int     `json:"AwayPointSpreadPayout"`

	// Total
	OverUnder   *float64 `json:"OverUnder"`
	OverPayout  *int     `json:"OverPayout"`
	UnderPayout *int     `json:"UnderPayout"`

	// Moneyline
	HomeMoneyline *int `json:"HomeMoneyLine"`
	AwayMoneyline *int `json:"AwayMoneyLine"`

	// Team Totals
	HomeTeamTotal *float64 `json:"HomeTeamTotal"`
	AwayTeamTotal *float64 `json:"AwayTeamTotal"`
}

// GameOddsResponse represents the game-level response from SportsDataIO odds API
type GameOddsResponse struct {
	GameID        int         `json:"GameId"`
	Season        int         `json:"Season"`
	Week          int         `json:"Week"`
	PregameOdds   []OddsInput `json:"PregameOdds"`
	LiveOdds      []OddsInput `json:"LiveOdds"`
	AlternateOdds []OddsInput `json:"AlternateMarketPregameOdds"`
}

// ToOdds converts OddsInput (from API) to Odds model
func (oi *OddsInput) ToOdds(dbGameID int) *Odds {
	// Determine market type based on populated fields
	marketType := "pregame"
	if oi.OddsType != "" {
		marketType = oi.OddsType
	}

	// Determine period (default to "Full Game" for pregame odds)
	period := "Full Game"

	odds := &Odds{
		GameID:       dbGameID,
		SportsbookID: strconv.Itoa(oi.SportsbookID),
		MarketType:   marketType,
		Period:       period,
		FetchedAt:    time.Now(),
	}

	if oi.SportsbookName != "" {
		odds.SportsbookName = sql.NullString{String: oi.SportsbookName, Valid: true}
	}

	// Spread
	if oi.HomeSpread != nil {
		odds.HomeSpread = sql.NullFloat64{Float64: *oi.HomeSpread, Valid: true}
	}
	if oi.AwaySpread != nil {
		odds.AwaySpread = sql.NullFloat64{Float64: *oi.AwaySpread, Valid: true}
	}
	if oi.HomeSpreadPayout != nil {
		odds.HomeSpreadJuice = sql.NullInt32{Int32: int32(*oi.HomeSpreadPayout), Valid: true}
	}
	if oi.AwaySpreadPayout != nil {
		odds.AwaySpreadJuice = sql.NullInt32{Int32: int32(*oi.AwaySpreadPayout), Valid: true}
	}

	// Total
	if oi.OverUnder != nil {
		odds.OverUnder = sql.NullFloat64{Float64: *oi.OverUnder, Valid: true}
	}
	if oi.OverPayout != nil {
		odds.OverJuice = sql.NullInt32{Int32: int32(*oi.OverPayout), Valid: true}
	}
	if oi.UnderPayout != nil {
		odds.UnderJuice = sql.NullInt32{Int32: int32(*oi.UnderPayout), Valid: true}
	}

	// Moneyline
	if oi.HomeMoneyline != nil {
		odds.HomeMoneyline = sql.NullInt32{Int32: int32(*oi.HomeMoneyline), Valid: true}
	}
	if oi.AwayMoneyline != nil {
		odds.AwayMoneyline = sql.NullInt32{Int32: int32(*oi.AwayMoneyline), Valid: true}
	}

	// Team Totals
	if oi.HomeTeamTotal != nil {
		odds.HomeTeamTotal = sql.NullFloat64{Float64: *oi.HomeTeamTotal, Valid: true}
	}
	if oi.AwayTeamTotal != nil {
		odds.AwayTeamTotal = sql.NullFloat64{Float64: *oi.AwayTeamTotal, Valid: true}
	}

	return odds
}

// LineMovement represents historical line movement tracking
type LineMovement struct {
	ID             int            `db:"id"`
	GameID         int            `db:"game_id"`
	SportsbookID   string         `db:"sportsbook_id"`
	SportsbookName sql.NullString `db:"sportsbook_name"`
	MarketType     string         `db:"market_type"`
	Period         string         `db:"period"`

	// Previous line
	PrevHomeSpread    sql.NullFloat64 `db:"prev_home_spread"`
	PrevAwaySpread    sql.NullFloat64 `db:"prev_away_spread"`
	PrevOverUnder     sql.NullFloat64 `db:"prev_over_under"`
	PrevHomeMoneyline sql.NullInt32   `db:"prev_home_moneyline"`
	PrevAwayMoneyline sql.NullInt32   `db:"prev_away_moneyline"`

	// New line
	NewHomeSpread    sql.NullFloat64 `db:"new_home_spread"`
	NewAwaySpread    sql.NullFloat64 `db:"new_away_spread"`
	NewOverUnder     sql.NullFloat64 `db:"new_over_under"`
	NewHomeMoneyline sql.NullInt32   `db:"new_home_moneyline"`
	NewAwayMoneyline sql.NullInt32   `db:"new_away_moneyline"`

	// Movement metadata
	MovementTimestamp time.Time       `db:"movement_timestamp"`
	MovementDirection sql.NullString  `db:"movement_direction"`
	MovementMagnitude sql.NullFloat64 `db:"movement_magnitude"`

	CreatedAt time.Time `db:"created_at"`
}

// DetectLineMovement creates a LineMovement record if odds have changed
func DetectLineMovement(prevOdds, newOdds *Odds) *LineMovement {
	// Check if there's any movement
	hasMovement := false

	if prevOdds.HomeSpread.Valid && newOdds.HomeSpread.Valid &&
		prevOdds.HomeSpread.Float64 != newOdds.HomeSpread.Float64 {
		hasMovement = true
	}
	if prevOdds.OverUnder.Valid && newOdds.OverUnder.Valid &&
		prevOdds.OverUnder.Float64 != newOdds.OverUnder.Float64 {
		hasMovement = true
	}

	if !hasMovement {
		return nil
	}

	movement := &LineMovement{
		GameID:            newOdds.GameID,
		SportsbookID:      newOdds.SportsbookID,
		SportsbookName:    newOdds.SportsbookName,
		MarketType:        newOdds.MarketType,
		Period:            newOdds.Period,
		MovementTimestamp: time.Now(),
	}

	// Previous line
	movement.PrevHomeSpread = prevOdds.HomeSpread
	movement.PrevAwaySpread = prevOdds.AwaySpread
	movement.PrevOverUnder = prevOdds.OverUnder
	movement.PrevHomeMoneyline = prevOdds.HomeMoneyline
	movement.PrevAwayMoneyline = prevOdds.AwayMoneyline

	// New line
	movement.NewHomeSpread = newOdds.HomeSpread
	movement.NewAwaySpread = newOdds.AwaySpread
	movement.NewOverUnder = newOdds.OverUnder
	movement.NewHomeMoneyline = newOdds.HomeMoneyline
	movement.NewAwayMoneyline = newOdds.AwayMoneyline

	// Calculate movement direction and magnitude
	if prevOdds.HomeSpread.Valid && newOdds.HomeSpread.Valid {
		diff := newOdds.HomeSpread.Float64 - prevOdds.HomeSpread.Float64
		if diff > 0 {
			movement.MovementDirection = sql.NullString{String: "toward_away", Valid: true}
		} else if diff < 0 {
			movement.MovementDirection = sql.NullString{String: "toward_home", Valid: true}
		}
		if diff != 0 {
			movement.MovementMagnitude = sql.NullFloat64{Float64: abs(diff), Valid: true}
		}
	}

	return movement
}

func abs(x float64) float64 {
	if x < 0 {
		return -x
	}
	return x
}
