package models

import (
	"database/sql"
	"time"
)

// Stadium represents a stadium where games are played
type Stadium struct {
	ID        int            `db:"id"`
	StadiumID int            `db:"stadium_id"`
	Name      string         `db:"name"`
	City      sql.NullString `db:"city"`
	State     sql.NullString `db:"state"`
	Country   sql.NullString `db:"country"`
	Capacity  sql.NullInt32  `db:"capacity"`
	Surface   sql.NullString `db:"surface"`
	CreatedAt time.Time      `db:"created_at"`
	UpdatedAt time.Time      `db:"updated_at"`
}

// StadiumInput is used for creating/updating stadiums from API
type StadiumInput struct {
	StadiumID int    `json:"StadiumID"`
	Name      string `json:"Name"`
	City      string `json:"City"`
	State     string `json:"State"`
	Country   string `json:"Country"`
	Capacity  *int   `json:"Capacity,omitempty"`
	Surface   string `json:"PlayingSurface"`
}

// ToStadium converts StadiumInput (from API) to Stadium model
func (si *StadiumInput) ToStadium() *Stadium {
	stadium := &Stadium{
		StadiumID: si.StadiumID,
		Name:      si.Name,
	}

	if si.City != "" {
		stadium.City = sql.NullString{String: si.City, Valid: true}
	}
	if si.State != "" {
		stadium.State = sql.NullString{String: si.State, Valid: true}
	}
	if si.Country != "" {
		stadium.Country = sql.NullString{String: si.Country, Valid: true}
	}
	if si.Capacity != nil && *si.Capacity > 0 {
		capacity := int32(*si.Capacity)
		stadium.Capacity = sql.NullInt32{Int32: capacity, Valid: true}
	}
	if si.Surface != "" {
		stadium.Surface = sql.NullString{String: si.Surface, Valid: true}
	}

	return stadium
}
