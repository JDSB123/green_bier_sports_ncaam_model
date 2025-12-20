package models

import (
	"database/sql"
	"time"
)

// Team represents a college football team
type Team struct {
	ID              int             `db:"id"`
	TeamID          int             `db:"team_id"`
	TeamCode        string          `db:"team_code"`
	SchoolName      string          `db:"school_name"`
	Mascot          sql.NullString  `db:"mascot"`
	Conference      sql.NullString  `db:"conference"`
	Division        sql.NullString  `db:"division"`
	TalentComposite sql.NullFloat64 `db:"talent_composite"`
	City            sql.NullString  `db:"city"`
	State           sql.NullString  `db:"state"`
	CreatedAt       time.Time       `db:"created_at"`
	UpdatedAt       time.Time       `db:"updated_at"`
}

// TeamInput is used for creating/updating teams
type TeamInput struct {
	TeamID          int      `json:"TeamID"`
	Key             string   `json:"Key"`    // API returns "Key" for team code
	School          string   `json:"School"` // School name
	Name            string   `json:"Name"`   // Mascot
	Conference      string   `json:"Conference"`
	Division        string   `json:"Division"`
	City            string   `json:"City"`
	State           string   `json:"State"`
	TalentComposite *float64 `json:"TalentComposite,omitempty"`
}

// ToTeam converts TeamInput (from API) to Team model
func (ti *TeamInput) ToTeam() *Team {
	team := &Team{
		TeamID:     ti.TeamID,
		TeamCode:   ti.Key,
		SchoolName: ti.School,
	}

	if ti.Name != "" {
		team.Mascot = sql.NullString{String: ti.Name, Valid: true}
	}
	if ti.Conference != "" {
		team.Conference = sql.NullString{String: ti.Conference, Valid: true}
	}
	if ti.Division != "" {
		team.Division = sql.NullString{String: ti.Division, Valid: true}
	}
	if ti.City != "" {
		team.City = sql.NullString{String: ti.City, Valid: true}
	}
	if ti.State != "" {
		team.State = sql.NullString{String: ti.State, Valid: true}
	}
	if ti.TalentComposite != nil {
		team.TalentComposite = sql.NullFloat64{Float64: *ti.TalentComposite, Valid: true}
	}

	return team
}
