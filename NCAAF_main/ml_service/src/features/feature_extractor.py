"""
Feature Extractor for NCAAF Predictions

Extracts predictive features from team statistics, games, and odds data.
Implements opponent adjustments, recent form, and efficiency metrics.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta


class FeatureExtractor:
    """
    Extracts features for college football game predictions.

    Key feature categories:
    - Team efficiency (yards per play, 3rd down %, red zone %)
    - QB performance metrics
    - Opponent-adjusted statistics
    - Recent form (last 3-5 games)
    - Home/away splits
    - Pace and tempo factors
    - Matchup-specific features
    """

    def __init__(self, db_connection):
        """
        Initialize feature extractor with database connection.

        Args:
            db_connection: Database connection for fetching team/game data
        """
        self.db = db_connection

    def extract_game_features(
        self,
        home_team_id: int,
        away_team_id: int,
        season: int,
        week: int
    ) -> Dict[str, float]:
        """
        Extract all features for a specific game matchup.

        Args:
            home_team_id: Database ID of home team
            away_team_id: Database ID of away team
            season: Season year
            week: Week number

        Returns:
            Dictionary of feature names to values
        """
        features = {}

        # Get team stats
        home_stats = self._get_team_stats(home_team_id, season)
        away_stats = self._get_team_stats(away_team_id, season)

        # Get recent form
        home_recent = self._get_recent_form(home_team_id, season, week, n_games=3)
        away_recent = self._get_recent_form(away_team_id, season, week, n_games=3)

        # Get home/away splits
        home_splits = self._get_home_away_splits(home_team_id, season, week, is_home=True)
        away_splits = self._get_home_away_splits(away_team_id, season, week, is_home=False)

        # Team efficiency features
        features.update(self._extract_efficiency_features(home_stats, prefix='home_'))
        features.update(self._extract_efficiency_features(away_stats, prefix='away_'))

        # QB features
        features.update(self._extract_qb_features(home_stats, prefix='home_'))
        features.update(self._extract_qb_features(away_stats, prefix='away_'))

        # Recent form features
        features.update(self._extract_recent_form_features(home_recent, prefix='home_'))
        features.update(self._extract_recent_form_features(away_recent, prefix='away_'))

        # Home/away split features
        features.update(self._extract_split_features(home_splits, prefix='home_'))
        features.update(self._extract_split_features(away_splits, prefix='away_'))

        # Matchup features (differential)
        features.update(self._extract_matchup_features(home_stats, away_stats))

        # Pace features
        features['home_pace'] = home_stats.get('yards_per_play', 0.0) or 0.0
        features['away_pace'] = away_stats.get('yards_per_play', 0.0) or 0.0
        features['pace_differential'] = features['home_pace'] - features['away_pace']

        # Talent composite (from recruiting rankings)
        features['home_talent_composite'] = self._get_talent_composite(home_team_id)
        features['away_talent_composite'] = self._get_talent_composite(away_team_id)
        features['talent_differential'] = features['home_talent_composite'] - features['away_talent_composite']

        return features

    def _get_team_stats(self, team_id: int, season: int) -> Dict[str, float]:
        """Fetch season stats for a team."""
        query = """
            SELECT
                points_per_game,
                yards_per_game,
                pass_yards_per_game,
                rush_yards_per_game,
                yards_per_play,
                points_allowed_per_game,
                yards_allowed_per_game,
                pass_yards_allowed_per_game,
                rush_yards_allowed_per_game,
                yards_per_play_allowed,
                third_down_conversion_pct,
                fourth_down_conversion_pct,
                red_zone_scoring_pct,
                turnovers,
                takeaways,
                turnover_margin,
                qb_rating,
                completion_percentage,
                passing_touchdowns,
                interceptions,
                wins,
                losses
            FROM team_season_stats
            WHERE team_id = %s AND season = %s
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (team_id, season))
                row = cur.fetchone()

                if not row:
                    # Return defaults if no stats found
                    return self._default_stats()

                return {
                    'points_per_game': float(row['points_per_game'] or 0),
                    'yards_per_game': float(row['yards_per_game'] or 0),
                    'pass_yards_per_game': float(row['pass_yards_per_game'] or 0),
                    'rush_yards_per_game': float(row['rush_yards_per_game'] or 0),
                    'yards_per_play': float(row['yards_per_play'] or 0),
                    'points_allowed_per_game': float(row['points_allowed_per_game'] or 0),
                    'yards_allowed_per_game': float(row['yards_allowed_per_game'] or 0),
                    'pass_yards_allowed_per_game': float(row['pass_yards_allowed_per_game'] or 0),
                    'rush_yards_allowed_per_game': float(row['rush_yards_allowed_per_game'] or 0),
                    'yards_per_play_allowed': float(row['yards_per_play_allowed'] or 0),
                    'third_down_conversion_pct': float(row['third_down_conversion_pct'] or 0),
                    'fourth_down_conversion_pct': float(row['fourth_down_conversion_pct'] or 0),
                    'red_zone_scoring_pct': float(row['red_zone_scoring_pct'] or 0),
                    'turnovers': float(row['turnovers'] or 0),
                    'takeaways': float(row['takeaways'] or 0),
                    'turnover_margin': float(row['turnover_margin'] or 0),
                    'qb_rating': float(row['qb_rating'] or 0),
                    'completion_percentage': float(row['completion_percentage'] or 0),
                    'passing_touchdowns': float(row['passing_touchdowns'] or 0),
                    'interceptions': float(row['interceptions'] or 0),
                    'wins': float(row['wins'] or 0),
                    'losses': float(row['losses'] or 0),
                }

    def _get_recent_form(
        self,
        team_id: int,
        season: int,
        current_week: int,
        n_games: int = 3
    ) -> List[Dict[str, float]]:
        """
        Get recent game performance for a team.

        Returns stats from last N games before current week.
        """
        query = """
            WITH team_games AS (
                SELECT
                    g.week,
                    g.game_date,
                    CASE
                        WHEN g.home_team_id = %s THEN g.home_score
                        ELSE g.away_score
                    END as team_score,
                    CASE
                        WHEN g.home_team_id = %s THEN g.away_score
                        ELSE g.home_score
                    END as opponent_score,
                    CASE
                        WHEN g.home_team_id = %s THEN 1
                        ELSE 0
                    END as is_home
                FROM games g
                WHERE (g.home_team_id = %s OR g.away_team_id = %s)
                  AND g.season = %s
                  AND g.week < %s
                  AND g.status = 'Final'
                ORDER BY g.week DESC
                LIMIT %s
            )
            SELECT
                team_score,
                opponent_score,
                is_home,
                (team_score - opponent_score) as margin
            FROM team_games
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (team_id, team_id, team_id, team_id, team_id, season, current_week, n_games)
                )
                rows = cur.fetchall()

                return [
                    {
                        'score': float(row['team_score'] or 0),
                        'opponent_score': float(row['opponent_score'] or 0),
                        'is_home': bool(row['is_home']),
                        'margin': float(row['margin'] or 0),
                    }
                    for row in rows
                ]

    def _get_home_away_splits(
        self,
        team_id: int,
        season: int,
        current_week: int,
        is_home: bool
    ) -> Dict[str, float]:
        """Get home or away performance splits."""
        home_filter = "g.home_team_id = %s" if is_home else "g.away_team_id = %s"
        score_field = "g.home_score" if is_home else "g.away_score"
        opp_score_field = "g.away_score" if is_home else "g.home_score"

        query = f"""
            SELECT
                AVG({score_field}) as avg_score,
                AVG({opp_score_field}) as avg_opp_score,
                AVG({score_field} - {opp_score_field}) as avg_margin,
                COUNT(*) as games_played
            FROM games g
            WHERE {home_filter}
              AND g.season = %s
              AND g.week < %s
              AND g.status = 'Final'
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (team_id, season, current_week))
                row = cur.fetchone()

                if not row or row['games_played'] == 0:
                    return {'avg_score': 0.0, 'avg_opp_score': 0.0, 'avg_margin': 0.0, 'games': 0}

                return {
                    'avg_score': float(row['avg_score'] or 0),
                    'avg_opp_score': float(row['avg_opp_score'] or 0),
                    'avg_margin': float(row['avg_margin'] or 0),
                    'games': int(row['games_played']),
                }

    def _get_talent_composite(self, team_id: int) -> float:
        """Get talent composite from recruiting rankings."""
        query = "SELECT talent_composite FROM teams WHERE id = %s"

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (team_id,))
                row = cur.fetchone()
                return float(row['talent_composite'] if row and row['talent_composite'] else 0.5)

    def _extract_efficiency_features(
        self,
        stats: Dict[str, float],
        prefix: str = ''
    ) -> Dict[str, float]:
        """Extract efficiency-based features."""
        return {
            f'{prefix}offensive_efficiency': stats.get('yards_per_play', 0.0),
            f'{prefix}defensive_efficiency': stats.get('yards_per_play_allowed', 0.0),
            f'{prefix}third_down_pct': stats.get('third_down_conversion_pct', 0.0),
            f'{prefix}red_zone_pct': stats.get('red_zone_scoring_pct', 0.0),
            f'{prefix}points_per_game': stats.get('points_per_game', 0.0),
            f'{prefix}points_allowed': stats.get('points_allowed_per_game', 0.0),
        }

    def _extract_qb_features(
        self,
        stats: Dict[str, float],
        prefix: str = ''
    ) -> Dict[str, float]:
        """Extract QB-related features."""
        return {
            f'{prefix}qb_rating': stats.get('qb_rating', 0.0),
            f'{prefix}completion_pct': stats.get('completion_percentage', 0.0),
            f'{prefix}pass_td_rate': stats.get('passing_touchdowns', 0.0),
            f'{prefix}int_rate': stats.get('interceptions', 0.0),
        }

    def _extract_recent_form_features(
        self,
        recent_games: List[Dict[str, float]],
        prefix: str = ''
    ) -> Dict[str, float]:
        """Extract recent form features."""
        if not recent_games:
            return {
                f'{prefix}recent_ppg': 0.0,
                f'{prefix}recent_margin': 0.0,
                f'{prefix}recent_wins': 0.0,
            }

        avg_score = np.mean([g['score'] for g in recent_games])
        avg_margin = np.mean([g['margin'] for g in recent_games])
        wins = sum(1 for g in recent_games if g['margin'] > 0)

        return {
            f'{prefix}recent_ppg': float(avg_score),
            f'{prefix}recent_margin': float(avg_margin),
            f'{prefix}recent_wins': float(wins),
        }

    def _extract_split_features(
        self,
        splits: Dict[str, float],
        prefix: str = ''
    ) -> Dict[str, float]:
        """Extract home/away split features."""
        return {
            f'{prefix}split_ppg': splits.get('avg_score', 0.0),
            f'{prefix}split_margin': splits.get('avg_margin', 0.0),
        }

    def _extract_matchup_features(
        self,
        home_stats: Dict[str, float],
        away_stats: Dict[str, float]
    ) -> Dict[str, float]:
        """Extract matchup differential features."""
        return {
            'offensive_diff': home_stats.get('yards_per_play', 0.0) - away_stats.get('yards_per_play', 0.0),
            'defensive_diff': away_stats.get('yards_per_play_allowed', 0.0) - home_stats.get('yards_per_play_allowed', 0.0),
            'turnover_diff': home_stats.get('turnover_margin', 0.0) - away_stats.get('turnover_margin', 0.0),
            'ppg_diff': home_stats.get('points_per_game', 0.0) - away_stats.get('points_per_game', 0.0),
        }

    def _default_stats(self) -> Dict[str, float]:
        """Return default stats when no data available."""
        return {
            'points_per_game': 0.0,
            'yards_per_game': 0.0,
            'pass_yards_per_game': 0.0,
            'rush_yards_per_game': 0.0,
            'yards_per_play': 0.0,
            'points_allowed_per_game': 0.0,
            'yards_allowed_per_game': 0.0,
            'pass_yards_allowed_per_game': 0.0,
            'rush_yards_allowed_per_game': 0.0,
            'yards_per_play_allowed': 0.0,
            'third_down_conversion_pct': 0.0,
            'fourth_down_conversion_pct': 0.0,
            'red_zone_scoring_pct': 0.0,
            'turnovers': 0.0,
            'takeaways': 0.0,
            'turnover_margin': 0.0,
            'qb_rating': 0.0,
            'completion_percentage': 0.0,
            'passing_touchdowns': 0.0,
            'interceptions': 0.0,
            'wins': 0.0,
            'losses': 0.0,
        }
