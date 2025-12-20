package repository

import (
	"context"
	"fmt"

	"ncaaf_v5/ingestion/internal/models"

	"github.com/rs/zerolog/log"
)

// ListUnpredictedGames retrieves all games that don't have predictions yet
func (r *GameRepository) ListUnpredictedGames(ctx context.Context) ([]*models.Game, error) {
	query := `
		SELECT g.id, g.game_id, g.season, g.week, g.status,
		       g.home_team_id, g.away_team_id, g.home_team_code, g.away_team_code,
		       g.game_date, g.stadium_id, g.period, g.time_remaining,
		       g.home_score, g.away_score,
		       g.home_score_quarter_1, g.home_score_quarter_2, g.home_score_quarter_3, g.home_score_quarter_4, g.home_score_overtime,
		       g.away_score_quarter_1, g.away_score_quarter_2, g.away_score_quarter_3, g.away_score_quarter_4, g.away_score_overtime,
		       g.total_score, g.margin, g.created_at, g.updated_at
		FROM games g
		LEFT JOIN predictions p ON g.id = p.game_id
		WHERE p.id IS NULL
		  AND g.status IN ('Scheduled', 'InProgress')
		ORDER BY g.game_date ASC
	`

	rows, err := r.db.Pool.Query(ctx, query)
	if err != nil {
		log.Error().Err(err).Msg("Failed to query unpredicted games")
		return nil, fmt.Errorf("failed to list unpredicted games: %w", err)
	}
	defer rows.Close()

	var games []*models.Game
	for rows.Next() {
		game := &models.Game{}
		if err := rows.Scan(
			&game.ID, &game.GameID, &game.Season, &game.Week, &game.Status,
			&game.HomeTeamID, &game.AwayTeamID, &game.HomeTeamCode, &game.AwayTeamCode,
			&game.GameDate, &game.StadiumID, &game.Period, &game.TimeRemaining,
			&game.HomeScore, &game.AwayScore,
			&game.HomeScoreQuarter1, &game.HomeScoreQuarter2, &game.HomeScoreQuarter3, &game.HomeScoreQuarter4, &game.HomeScoreOvertime,
			&game.AwayScoreQuarter1, &game.AwayScoreQuarter2, &game.AwayScoreQuarter3, &game.AwayScoreQuarter4, &game.AwayScoreOvertime,
			&game.TotalScore, &game.Margin, &game.CreatedAt, &game.UpdatedAt,
		); err != nil {
			log.Error().Err(err).Msg("Failed to scan game row")
			continue
		}
		games = append(games, game)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating game rows: %w", err)
	}

	log.Info().Int("count", len(games)).Msg("Unpredicted games retrieved")
	return games, nil
}
