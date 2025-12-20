package repository

import (
	"context"
	"fmt"

	"ncaaf_v5/ingestion/internal/models"

	"github.com/jackc/pgx/v5"
	"github.com/rs/zerolog/log"
)

// StatsRepository handles team season stats database operations
type StatsRepository struct {
	db *Database
}

// Create inserts new team season stats
func (r *StatsRepository) Create(ctx context.Context, stats *models.TeamSeasonStats) error {
	query := `
		INSERT INTO team_season_stats (
			team_id, season,
			points_per_game, yards_per_game, pass_yards_per_game, rush_yards_per_game, yards_per_play,
			points_allowed_per_game, yards_allowed_per_game, pass_yards_allowed_per_game,
			rush_yards_allowed_per_game, yards_per_play_allowed,
			third_down_conversion_pct, fourth_down_conversion_pct, red_zone_scoring_pct,
			turnovers, takeaways, turnover_margin,
			punt_return_yards_per_attempt, kick_return_yards_per_attempt,
			qb_rating, completion_percentage, passing_touchdowns, interceptions,
			wins, losses
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26)
		RETURNING id, created_at, updated_at
	`

	err := r.db.Pool.QueryRow(
		ctx, query,
		stats.TeamID, stats.Season,
		stats.PointsPerGame, stats.YardsPerGame, stats.PassYardsPerGame, stats.RushYardsPerGame, stats.YardsPerPlay,
		stats.PointsAllowedPerGame, stats.YardsAllowedPerGame, stats.PassYardsAllowedPerGame,
		stats.RushYardsAllowedPerGame, stats.YardsPerPlayAllowed,
		stats.ThirdDownConversionPct, stats.FourthDownConversionPct, stats.RedZoneScoringPct,
		stats.Turnovers, stats.Takeaways, stats.TurnoverMargin,
		stats.PuntReturnYardsPerAttempt, stats.KickReturnYardsPerAttempt,
		stats.QBRating, stats.CompletionPercentage, stats.PassingTouchdowns, stats.Interceptions,
		stats.Wins, stats.Losses,
	).Scan(&stats.ID, &stats.CreatedAt, &stats.UpdatedAt)

	if err != nil {
		return fmt.Errorf("failed to create team season stats: %w", err)
	}

	log.Debug().
		Int("team_id", stats.TeamID).
		Int("season", stats.Season).
		Msg("Team season stats created")

	return nil
}

// Upsert inserts or updates team season stats
func (r *StatsRepository) Upsert(ctx context.Context, stats *models.TeamSeasonStats) error {
	query := `
		INSERT INTO team_season_stats (
			team_id, season,
			points_per_game, yards_per_game, pass_yards_per_game, rush_yards_per_game, yards_per_play,
			points_allowed_per_game, yards_allowed_per_game, pass_yards_allowed_per_game,
			rush_yards_allowed_per_game, yards_per_play_allowed,
			third_down_conversion_pct, fourth_down_conversion_pct, red_zone_scoring_pct,
			turnovers, takeaways, turnover_margin,
			punt_return_yards_per_attempt, kick_return_yards_per_attempt,
			qb_rating, completion_percentage, passing_touchdowns, interceptions,
			wins, losses
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26)
		ON CONFLICT (team_id, season) DO UPDATE SET
			points_per_game = EXCLUDED.points_per_game,
			yards_per_game = EXCLUDED.yards_per_game,
			pass_yards_per_game = EXCLUDED.pass_yards_per_game,
			rush_yards_per_game = EXCLUDED.rush_yards_per_game,
			yards_per_play = EXCLUDED.yards_per_play,
			points_allowed_per_game = EXCLUDED.points_allowed_per_game,
			yards_allowed_per_game = EXCLUDED.yards_allowed_per_game,
			pass_yards_allowed_per_game = EXCLUDED.pass_yards_allowed_per_game,
			rush_yards_allowed_per_game = EXCLUDED.rush_yards_allowed_per_game,
			yards_per_play_allowed = EXCLUDED.yards_per_play_allowed,
			third_down_conversion_pct = EXCLUDED.third_down_conversion_pct,
			fourth_down_conversion_pct = EXCLUDED.fourth_down_conversion_pct,
			red_zone_scoring_pct = EXCLUDED.red_zone_scoring_pct,
			turnovers = EXCLUDED.turnovers,
			takeaways = EXCLUDED.takeaways,
			turnover_margin = EXCLUDED.turnover_margin,
			punt_return_yards_per_attempt = EXCLUDED.punt_return_yards_per_attempt,
			kick_return_yards_per_attempt = EXCLUDED.kick_return_yards_per_attempt,
			qb_rating = EXCLUDED.qb_rating,
			completion_percentage = EXCLUDED.completion_percentage,
			passing_touchdowns = EXCLUDED.passing_touchdowns,
			interceptions = EXCLUDED.interceptions,
			wins = EXCLUDED.wins,
			losses = EXCLUDED.losses,
			updated_at = NOW()
		RETURNING id, created_at, updated_at
	`

	err := r.db.Pool.QueryRow(
		ctx, query,
		stats.TeamID, stats.Season,
		stats.PointsPerGame, stats.YardsPerGame, stats.PassYardsPerGame, stats.RushYardsPerGame, stats.YardsPerPlay,
		stats.PointsAllowedPerGame, stats.YardsAllowedPerGame, stats.PassYardsAllowedPerGame,
		stats.RushYardsAllowedPerGame, stats.YardsPerPlayAllowed,
		stats.ThirdDownConversionPct, stats.FourthDownConversionPct, stats.RedZoneScoringPct,
		stats.Turnovers, stats.Takeaways, stats.TurnoverMargin,
		stats.PuntReturnYardsPerAttempt, stats.KickReturnYardsPerAttempt,
		stats.QBRating, stats.CompletionPercentage, stats.PassingTouchdowns, stats.Interceptions,
		stats.Wins, stats.Losses,
	).Scan(&stats.ID, &stats.CreatedAt, &stats.UpdatedAt)

	if err != nil {
		return fmt.Errorf("failed to upsert team season stats: %w", err)
	}

	return nil
}

// GetByTeamAndSeason retrieves stats for a team in a specific season
func (r *StatsRepository) GetByTeamAndSeason(ctx context.Context, teamID, season int) (*models.TeamSeasonStats, error) {
	query := `
		SELECT id, team_id, season,
		       points_per_game, yards_per_game, pass_yards_per_game, rush_yards_per_game, yards_per_play,
		       points_allowed_per_game, yards_allowed_per_game, pass_yards_allowed_per_game,
		       rush_yards_allowed_per_game, yards_per_play_allowed,
		       third_down_conversion_pct, fourth_down_conversion_pct, red_zone_scoring_pct,
		       turnovers, takeaways, turnover_margin,
		       punt_return_yards_per_attempt, kick_return_yards_per_attempt,
		       qb_rating, completion_percentage, passing_touchdowns, interceptions,
		       wins, losses,
		       created_at, updated_at
		FROM team_season_stats
		WHERE team_id = $1 AND season = $2
	`

	var stats models.TeamSeasonStats
	err := r.db.Pool.QueryRow(ctx, query, teamID, season).Scan(
		&stats.ID, &stats.TeamID, &stats.Season,
		&stats.PointsPerGame, &stats.YardsPerGame, &stats.PassYardsPerGame, &stats.RushYardsPerGame, &stats.YardsPerPlay,
		&stats.PointsAllowedPerGame, &stats.YardsAllowedPerGame, &stats.PassYardsAllowedPerGame,
		&stats.RushYardsAllowedPerGame, &stats.YardsPerPlayAllowed,
		&stats.ThirdDownConversionPct, &stats.FourthDownConversionPct, &stats.RedZoneScoringPct,
		&stats.Turnovers, &stats.Takeaways, &stats.TurnoverMargin,
		&stats.PuntReturnYardsPerAttempt, &stats.KickReturnYardsPerAttempt,
		&stats.QBRating, &stats.CompletionPercentage, &stats.PassingTouchdowns, &stats.Interceptions,
		&stats.Wins, &stats.Losses,
		&stats.CreatedAt, &stats.UpdatedAt,
	)

	if err == pgx.ErrNoRows {
		return nil, fmt.Errorf("stats not found: team_id=%d, season=%d", teamID, season)
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get team season stats: %w", err)
	}

	return &stats, nil
}

// GetBySeason retrieves all team stats for a specific season
func (r *StatsRepository) GetBySeason(ctx context.Context, season int) ([]*models.TeamSeasonStats, error) {
	query := `
		SELECT id, team_id, season,
		       points_per_game, yards_per_game, pass_yards_per_game, rush_yards_per_game, yards_per_play,
		       points_allowed_per_game, yards_allowed_per_game, pass_yards_allowed_per_game,
		       rush_yards_allowed_per_game, yards_per_play_allowed,
		       third_down_conversion_pct, fourth_down_conversion_pct, red_zone_scoring_pct,
		       turnovers, takeaways, turnover_margin,
		       punt_return_yards_per_attempt, kick_return_yards_per_attempt,
		       qb_rating, completion_percentage, passing_touchdowns, interceptions,
		       wins, losses,
		       created_at, updated_at
		FROM team_season_stats
		WHERE season = $1
		ORDER BY points_per_game DESC
	`

	rows, err := r.db.Pool.Query(ctx, query, season)
	if err != nil {
		return nil, fmt.Errorf("failed to get season stats: %w", err)
	}
	defer rows.Close()

	var statsList []*models.TeamSeasonStats
	for rows.Next() {
		var stats models.TeamSeasonStats
		err := rows.Scan(
			&stats.ID, &stats.TeamID, &stats.Season,
			&stats.PointsPerGame, &stats.YardsPerGame, &stats.PassYardsPerGame, &stats.RushYardsPerGame, &stats.YardsPerPlay,
			&stats.PointsAllowedPerGame, &stats.YardsAllowedPerGame, &stats.PassYardsAllowedPerGame,
			&stats.RushYardsAllowedPerGame, &stats.YardsPerPlayAllowed,
			&stats.ThirdDownConversionPct, &stats.FourthDownConversionPct, &stats.RedZoneScoringPct,
			&stats.Turnovers, &stats.Takeaways, &stats.TurnoverMargin,
			&stats.PuntReturnYardsPerAttempt, &stats.KickReturnYardsPerAttempt,
			&stats.QBRating, &stats.CompletionPercentage, &stats.PassingTouchdowns, &stats.Interceptions,
			&stats.Wins, &stats.Losses,
			&stats.CreatedAt, &stats.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan stats: %w", err)
		}
		statsList = append(statsList, &stats)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating stats: %w", err)
	}

	return statsList, nil
}

// Delete deletes team season stats
func (r *StatsRepository) Delete(ctx context.Context, teamID, season int) error {
	query := `DELETE FROM team_season_stats WHERE team_id = $1 AND season = $2`

	result, err := r.db.Pool.Exec(ctx, query, teamID, season)
	if err != nil {
		return fmt.Errorf("failed to delete stats: %w", err)
	}

	if result.RowsAffected() == 0 {
		return fmt.Errorf("stats not found: team_id=%d, season=%d", teamID, season)
	}

	log.Debug().
		Int("team_id", teamID).
		Int("season", season).
		Msg("Team season stats deleted")

	return nil
}
