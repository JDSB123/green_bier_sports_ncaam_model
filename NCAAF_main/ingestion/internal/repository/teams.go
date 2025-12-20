package repository

import (
	"context"
	"fmt"

	"ncaaf_v5/ingestion/internal/models"

	"github.com/jackc/pgx/v5"
	"github.com/rs/zerolog/log"
)

// TeamRepository handles team database operations
type TeamRepository struct {
	db *Database
}

// Create inserts a new team
func (r *TeamRepository) Create(ctx context.Context, team *models.Team) error {
	query := `
		INSERT INTO teams (
			team_id, team_code, school_name, mascot, conference, division,
			talent_composite, city, state
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
		RETURNING id, created_at, updated_at
	`

	err := r.db.Pool.QueryRow(
		ctx, query,
		team.TeamID, team.TeamCode, team.SchoolName, team.Mascot,
		team.Conference, team.Division, team.TalentComposite,
		team.City, team.State,
	).Scan(&team.ID, &team.CreatedAt, &team.UpdatedAt)

	if err != nil {
		return fmt.Errorf("failed to create team: %w", err)
	}

	log.Debug().
		Int("id", team.ID).
		Int("team_id", team.TeamID).
		Str("code", team.TeamCode).
		Str("school", team.SchoolName).
		Msg("Team created")

	return nil
}

// Upsert inserts or updates a team (for nightly refresh)
func (r *TeamRepository) Upsert(ctx context.Context, team *models.Team) error {
	query := `
		INSERT INTO teams (
			team_id, team_code, school_name, mascot, conference, division,
			talent_composite, city, state
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
		ON CONFLICT (team_id) DO UPDATE SET
			team_code = EXCLUDED.team_code,
			school_name = EXCLUDED.school_name,
			mascot = EXCLUDED.mascot,
			conference = EXCLUDED.conference,
			division = EXCLUDED.division,
			talent_composite = EXCLUDED.talent_composite,
			city = EXCLUDED.city,
			state = EXCLUDED.state,
			updated_at = NOW()
		RETURNING id, created_at, updated_at
	`

	err := r.db.Pool.QueryRow(
		ctx, query,
		team.TeamID, team.TeamCode, team.SchoolName, team.Mascot,
		team.Conference, team.Division, team.TalentComposite,
		team.City, team.State,
	).Scan(&team.ID, &team.CreatedAt, &team.UpdatedAt)

	if err != nil {
		return fmt.Errorf("failed to upsert team: %w", err)
	}

	return nil
}

// GetByID retrieves a team by its database ID
func (r *TeamRepository) GetByID(ctx context.Context, id int) (*models.Team, error) {
	query := `
		SELECT id, team_id, team_code, school_name, mascot, conference, division,
		       talent_composite, city, state, created_at, updated_at
		FROM teams
		WHERE id = $1
	`

	var team models.Team
	err := r.db.Pool.QueryRow(ctx, query, id).Scan(
		&team.ID, &team.TeamID, &team.TeamCode, &team.SchoolName,
		&team.Mascot, &team.Conference, &team.Division,
		&team.TalentComposite, &team.City, &team.State,
		&team.CreatedAt, &team.UpdatedAt,
	)

	if err == pgx.ErrNoRows {
		return nil, fmt.Errorf("team not found: id=%d", id)
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get team: %w", err)
	}

	return &team, nil
}

// GetByTeamID retrieves a team by its SportsDataIO TeamID
func (r *TeamRepository) GetByTeamID(ctx context.Context, teamID int) (*models.Team, error) {
	query := `
		SELECT id, team_id, team_code, school_name, mascot, conference, division,
		       talent_composite, city, state, created_at, updated_at
		FROM teams
		WHERE team_id = $1
	`

	var team models.Team
	err := r.db.Pool.QueryRow(ctx, query, teamID).Scan(
		&team.ID, &team.TeamID, &team.TeamCode, &team.SchoolName,
		&team.Mascot, &team.Conference, &team.Division,
		&team.TalentComposite, &team.City, &team.State,
		&team.CreatedAt, &team.UpdatedAt,
	)

	if err == pgx.ErrNoRows {
		return nil, fmt.Errorf("team not found: team_id=%d", teamID)
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get team: %w", err)
	}

	return &team, nil
}

// GetByTeamCode retrieves a team by its team code
func (r *TeamRepository) GetByTeamCode(ctx context.Context, teamCode string) (*models.Team, error) {
	query := `
		SELECT id, team_id, team_code, school_name, mascot, conference, division,
		       talent_composite, city, state, created_at, updated_at
		FROM teams
		WHERE team_code = $1
	`

	var team models.Team
	err := r.db.Pool.QueryRow(ctx, query, teamCode).Scan(
		&team.ID, &team.TeamID, &team.TeamCode, &team.SchoolName,
		&team.Mascot, &team.Conference, &team.Division,
		&team.TalentComposite, &team.City, &team.State,
		&team.CreatedAt, &team.UpdatedAt,
	)

	if err == pgx.ErrNoRows {
		return nil, fmt.Errorf("team not found: team_code=%s", teamCode)
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get team: %w", err)
	}

	return &team, nil
}

// List retrieves all teams
func (r *TeamRepository) List(ctx context.Context) ([]*models.Team, error) {
	query := `
		SELECT id, team_id, team_code, school_name, mascot, conference, division,
		       talent_composite, city, state, created_at, updated_at
		FROM teams
		ORDER BY school_name
	`

	rows, err := r.db.Pool.Query(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("failed to list teams: %w", err)
	}
	defer rows.Close()

	var teams []*models.Team
	for rows.Next() {
		var team models.Team
		err := rows.Scan(
			&team.ID, &team.TeamID, &team.TeamCode, &team.SchoolName,
			&team.Mascot, &team.Conference, &team.Division,
			&team.TalentComposite, &team.City, &team.State,
			&team.CreatedAt, &team.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan team: %w", err)
		}
		teams = append(teams, &team)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating teams: %w", err)
	}

	return teams, nil
}

// ListByConference retrieves teams by conference
func (r *TeamRepository) ListByConference(ctx context.Context, conference string) ([]*models.Team, error) {
	query := `
		SELECT id, team_id, team_code, school_name, mascot, conference, division,
		       talent_composite, city, state, created_at, updated_at
		FROM teams
		WHERE conference = $1
		ORDER BY school_name
	`

	rows, err := r.db.Pool.Query(ctx, query, conference)
	if err != nil {
		return nil, fmt.Errorf("failed to list teams by conference: %w", err)
	}
	defer rows.Close()

	var teams []*models.Team
	for rows.Next() {
		var team models.Team
		err := rows.Scan(
			&team.ID, &team.TeamID, &team.TeamCode, &team.SchoolName,
			&team.Mascot, &team.Conference, &team.Division,
			&team.TalentComposite, &team.City, &team.State,
			&team.CreatedAt, &team.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan team: %w", err)
		}
		teams = append(teams, &team)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating teams: %w", err)
	}

	return teams, nil
}

// Update updates a team
func (r *TeamRepository) Update(ctx context.Context, team *models.Team) error {
	query := `
		UPDATE teams SET
			team_code = $1,
			school_name = $2,
			mascot = $3,
			conference = $4,
			division = $5,
			talent_composite = $6,
			city = $7,
			state = $8,
			updated_at = NOW()
		WHERE id = $9
		RETURNING updated_at
	`

	err := r.db.Pool.QueryRow(
		ctx, query,
		team.TeamCode, team.SchoolName, team.Mascot,
		team.Conference, team.Division, team.TalentComposite,
		team.City, team.State, team.ID,
	).Scan(&team.UpdatedAt)

	if err == pgx.ErrNoRows {
		return fmt.Errorf("team not found: id=%d", team.ID)
	}
	if err != nil {
		return fmt.Errorf("failed to update team: %w", err)
	}

	return nil
}

// Delete deletes a team
func (r *TeamRepository) Delete(ctx context.Context, id int) error {
	query := `DELETE FROM teams WHERE id = $1`

	result, err := r.db.Pool.Exec(ctx, query, id)
	if err != nil {
		return fmt.Errorf("failed to delete team: %w", err)
	}

	if result.RowsAffected() == 0 {
		return fmt.Errorf("team not found: id=%d", id)
	}

	log.Debug().Int("id", id).Msg("Team deleted")
	return nil
}

// Count returns the total number of teams
func (r *TeamRepository) Count(ctx context.Context) (int, error) {
	query := `SELECT COUNT(*) FROM teams`

	var count int
	err := r.db.Pool.QueryRow(ctx, query).Scan(&count)
	if err != nil {
		return 0, fmt.Errorf("failed to count teams: %w", err)
	}

	return count, nil
}
