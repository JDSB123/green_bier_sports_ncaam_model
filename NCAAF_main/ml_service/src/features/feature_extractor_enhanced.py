"""
Enhanced Feature Extractor for NCAAF Predictions

Implements advanced feature engineering including:
- Line movement features (sharp vs public money)
- Opponent-adjusted efficiency metrics
- Havoc and explosive play metrics
- 5-game rolling averages
- Advanced pace and tempo features
- Strength of schedule adjustments
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class EnhancedFeatureExtractor:
    """
    Enhanced feature extraction with advanced metrics.

    Key improvements:
    - Line movement tracking (sharp vs public money)
    - Opponent-adjusted statistics
    - Havoc rate metrics
    - Explosive play tendencies
    - 5-game rolling windows
    - SRS (Simple Rating System) implementation
    """

    def __init__(self, db_connection):
        """
        Initialize enhanced feature extractor.

        Args:
            db_connection: Database connection for fetching data
        """
        self.db = db_connection
        self._cache = {}

    def extract_game_features(
        self,
        home_team_id: int,
        away_team_id: int,
        season: int,
        week: int,
        game_id: Optional[int] = None
    ) -> Dict[str, float]:
        """
        Extract all features including enhanced metrics.

        Args:
            home_team_id: Database ID of home team
            away_team_id: Database ID of away team
            season: Season year
            week: Week number
            game_id: Optional game ID for line movement features

        Returns:
            Dictionary of feature names to values
        """
        features = {}

        # Get team stats with caching
        home_stats = self._get_team_stats(home_team_id, season)
        away_stats = self._get_team_stats(away_team_id, season)

        # Get opponent-adjusted stats
        home_adj_stats = self._get_opponent_adjusted_stats(home_team_id, season, week)
        away_adj_stats = self._get_opponent_adjusted_stats(away_team_id, season, week)

        # Get recent form (5-game rolling window)
        home_recent = self._get_recent_form(home_team_id, season, week, n_games=5)
        away_recent = self._get_recent_form(away_team_id, season, week, n_games=5)

        # Get home/away splits
        home_splits = self._get_home_away_splits(home_team_id, season, week, is_home=True)
        away_splits = self._get_home_away_splits(away_team_id, season, week, is_home=False)

        # Basic efficiency features
        features.update(self._extract_efficiency_features(home_stats, prefix='home_'))
        features.update(self._extract_efficiency_features(away_stats, prefix='away_'))

        # Opponent-adjusted efficiency
        features.update(self._extract_opponent_adjusted_features(home_adj_stats, prefix='home_adj_'))
        features.update(self._extract_opponent_adjusted_features(away_adj_stats, prefix='away_adj_'))

        # QB features
        features.update(self._extract_qb_features(home_stats, prefix='home_'))
        features.update(self._extract_qb_features(away_stats, prefix='away_'))

        # Recent form features (5-game window)
        features.update(self._extract_recent_form_features(home_recent, prefix='home_'))
        features.update(self._extract_recent_form_features(away_recent, prefix='away_'))

        # Home/away split features
        features.update(self._extract_split_features(home_splits, prefix='home_'))
        features.update(self._extract_split_features(away_splits, prefix='away_'))

        # Havoc metrics
        home_havoc = self._get_havoc_metrics(home_team_id, season, week)
        away_havoc = self._get_havoc_metrics(away_team_id, season, week)
        features.update(self._extract_havoc_features(home_havoc, prefix='home_'))
        features.update(self._extract_havoc_features(away_havoc, prefix='away_'))

        # Explosive play metrics
        home_explosive = self._get_explosive_play_metrics(home_team_id, season, week)
        away_explosive = self._get_explosive_play_metrics(away_team_id, season, week)
        features.update(self._extract_explosive_features(home_explosive, prefix='home_'))
        features.update(self._extract_explosive_features(away_explosive, prefix='away_'))

        # Line movement features (if game_id provided)
        if game_id:
            line_features = self._extract_line_movement_features(game_id)
            features.update(line_features)

        # Matchup differentials
        features.update(self._extract_matchup_features(home_stats, away_stats))
        features.update(self._extract_adjusted_matchup_features(home_adj_stats, away_adj_stats))

        # Advanced pace and tempo
        features['home_pace'] = self._calculate_pace(home_stats)
        features['away_pace'] = self._calculate_pace(away_stats)
        features['pace_differential'] = features['home_pace'] - features['away_pace']
        features['tempo_factor'] = self._calculate_tempo_factor(home_stats, away_stats)

        # Simple Rating System (SRS)
        features['home_srs'] = self._calculate_srs(home_team_id, season, week)
        features['away_srs'] = self._calculate_srs(away_team_id, season, week)
        features['srs_differential'] = features['home_srs'] - features['away_srs']

        # Talent and recruiting
        features['home_talent_composite'] = self._get_talent_composite(home_team_id)
        features['away_talent_composite'] = self._get_talent_composite(away_team_id)
        features['talent_differential'] = features['home_talent_composite'] - features['away_talent_composite']

        # Strength of schedule
        features['home_sos'] = self._calculate_strength_of_schedule(home_team_id, season, week)
        features['away_sos'] = self._calculate_strength_of_schedule(away_team_id, season, week)
        features['sos_differential'] = features['home_sos'] - features['away_sos']

        return features

    def _get_opponent_adjusted_stats(self, team_id: int, season: int, week: int) -> Dict:
        """Calculate opponent-adjusted statistics."""
        query = """
            WITH opponent_stats AS (
                SELECT
                    g.game_id,
                    g.week,
                    CASE
                        WHEN g.home_team_id = %s THEN g.away_team_id
                        ELSE g.home_team_id
                    END as opponent_id,
                    CASE
                        WHEN g.home_team_id = %s THEN g.home_score
                        ELSE g.away_score
                    END as team_score,
                    CASE
                        WHEN g.home_team_id = %s THEN g.away_score
                        ELSE g.home_score
                    END as opponent_score
                FROM games g
                WHERE (g.home_team_id = %s OR g.away_team_id = %s)
                  AND g.season = %s
                  AND g.week < %s
                  AND g.status IN ('Final', 'F/OT')
            )
            SELECT
                os.*,
                tss.yards_allowed_per_game as opp_def_efficiency,
                tss.yards_per_game as opp_off_efficiency,
                tss.points_allowed_per_game as opp_points_allowed,
                tss.points_per_game as opp_points_per_game
            FROM opponent_stats os
            LEFT JOIN team_season_stats tss
                ON os.opponent_id = tss.team_id
                AND tss.season = %s
        """

        results = self.db.fetch_all(query, (team_id, team_id, team_id, team_id, team_id,
                                            season, week, season))

        if not results:
            return {}

        # Calculate opponent-adjusted metrics
        adjusted_stats = {
            'offensive_efficiency': 0.0,
            'defensive_efficiency': 0.0,
            'points_per_game': 0.0,
            'points_allowed': 0.0,
            'epa_per_play': 0.0,
            'success_rate': 0.0
        }

        weights = []
        for game in results:
            # Weight by opponent quality
            opp_quality = (game.get('opp_def_efficiency', 100) or 100) / 100.0
            weights.append(1.0 + (opp_quality - 1.0) * 0.5)  # Moderate weight adjustment

        if weights:
            # Calculate weighted averages
            total_weight = sum(weights)
            for i, game in enumerate(results):
                weight_factor = weights[i] / total_weight
                adjusted_stats['points_per_game'] += (game.get('team_score', 0) or 0) * weight_factor
                adjusted_stats['points_allowed'] += (game.get('opponent_score', 0) or 0) * weight_factor

            # Calculate efficiency metrics
            adjusted_stats['offensive_efficiency'] = adjusted_stats['points_per_game'] / max(len(results), 1)
            adjusted_stats['defensive_efficiency'] = adjusted_stats['points_allowed'] / max(len(results), 1)

            # Expected Points Added (simplified)
            adjusted_stats['epa_per_play'] = (adjusted_stats['points_per_game'] - 24.0) / 70.0

            # Success rate (simplified - % of games scoring above average)
            avg_score = sum(g.get('team_score', 0) or 0 for g in results) / max(len(results), 1)
            adjusted_stats['success_rate'] = sum(1 for g in results
                                                if (g.get('team_score', 0) or 0) > avg_score) / max(len(results), 1)

        return adjusted_stats

    def _get_havoc_metrics(self, team_id: int, season: int, week: int) -> Dict:
        """Get defensive havoc metrics."""
        # Check if team_game_stats table exists, if not return defaults
        try:
            query = """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'team_game_stats'
                )
            """
            table_exists = self.db.fetch_one(query)
            if not table_exists or not table_exists.get('exists', False):
                return {
                    'tackles_for_loss_rate': 0.0,
                    'sacks_per_dropback': 0.0,
                    'turnover_rate': 0.0,
                    'havoc_rate_total': 0.0,
                    'pass_breakup_rate': 0.0
                }
        except Exception:
            # If we can't check, return defaults
            return {
                'tackles_for_loss_rate': 0.0,
                'sacks_per_dropback': 0.0,
                'turnover_rate': 0.0,
                'havoc_rate_total': 0.0,
                'pass_breakup_rate': 0.0
            }

        query = """
            SELECT
                AVG(COALESCE(tackles_for_loss, 0)) as avg_tfl,
                AVG(COALESCE(sacks, 0)) as avg_sacks,
                AVG(COALESCE(interceptions, 0)) as avg_ints,
                AVG(COALESCE(forced_fumbles, 0)) as avg_forced_fumbles,
                AVG(COALESCE(pass_breakups, 0)) as avg_pbu,
                AVG(COALESCE(defensive_plays, 100)) as avg_def_plays
            FROM team_game_stats
            WHERE team_id = %s
              AND season = %s
              AND week < %s
        """

        try:
            result = self.db.fetch_one(query, (team_id, season, week))
        except Exception:
            # Table doesn't exist or query failed, return defaults
            return {
                'tackles_for_loss_rate': 0.0,
                'sacks_per_dropback': 0.0,
                'turnover_rate': 0.0,
                'havoc_rate_total': 0.0,
                'pass_breakup_rate': 0.0
            }

        if not result:
            return {
                'tackles_for_loss_rate': 0.0,
                'sacks_per_dropback': 0.0,
                'turnover_rate': 0.0,
                'havoc_rate_total': 0.0,
                'pass_breakup_rate': 0.0
            }

        def_plays = result.get('avg_def_plays', 100) or 100

        return {
            'tackles_for_loss_rate': (result.get('avg_tfl', 0) or 0) / def_plays,
            'sacks_per_dropback': (result.get('avg_sacks', 0) or 0) / max(def_plays * 0.4, 1),
            'turnover_rate': ((result.get('avg_ints', 0) or 0) +
                             (result.get('avg_forced_fumbles', 0) or 0)) / def_plays,
            'havoc_rate_total': ((result.get('avg_tfl', 0) or 0) +
                                (result.get('avg_sacks', 0) or 0) +
                                (result.get('avg_pbu', 0) or 0)) / def_plays,
            'pass_breakup_rate': (result.get('avg_pbu', 0) or 0) / max(def_plays * 0.4, 1)
        }

    def _get_explosive_play_metrics(self, team_id: int, season: int, week: int) -> Dict:
        """Get offensive explosive play tendencies."""
        # Check if team_game_stats table exists, if not return defaults
        try:
            query = """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'team_game_stats'
                )
            """
            table_exists = self.db.fetch_one(query)
            if not table_exists or not table_exists.get('exists', False):
                return {
                    'explosive_rush_rate': 0.0,
                    'explosive_pass_rate': 0.0,
                    'explosive_play_rate': 0.0,
                    'big_play_rate': 0.0,
                    'scoring_opportunity_rate': 0.0
                }
        except Exception:
            # If we can't check, return defaults
            return {
                'explosive_rush_rate': 0.0,
                'explosive_pass_rate': 0.0,
                'explosive_play_rate': 0.0,
                'big_play_rate': 0.0,
                'scoring_opportunity_rate': 0.0
            }

        query = """
            SELECT
                AVG(COALESCE(rushing_yards, 0) / NULLIF(rushing_attempts, 0)) as avg_ypc,
                AVG(COALESCE(passing_yards, 0) / NULLIF(passing_attempts, 0)) as avg_ypa,
                AVG(COALESCE(plays_20_plus, 0)) as avg_explosive_plays,
                AVG(COALESCE(plays_40_plus, 0)) as avg_big_plays,
                AVG(COALESCE(total_plays, 100)) as avg_total_plays,
                AVG(COALESCE(scoring_opportunities, 0)) as avg_scoring_opps
            FROM team_game_stats
            WHERE team_id = %s
              AND season = %s
              AND week < %s
        """

        try:
            result = self.db.fetch_one(query, (team_id, season, week))
        except Exception:
            # Table doesn't exist or query failed, return defaults
            return {
                'explosive_rush_rate': 0.0,
                'explosive_pass_rate': 0.0,
                'explosive_play_rate': 0.0,
                'big_play_rate': 0.0,
                'scoring_opportunity_rate': 0.0
            }

        if not result:
            return {
                'explosive_rush_rate': 0.0,
                'explosive_pass_rate': 0.0,
                'explosive_play_rate': 0.0,
                'big_play_rate': 0.0,
                'scoring_opportunity_rate': 0.0
            }

        total_plays = result.get('avg_total_plays', 100) or 100

        return {
            'explosive_rush_rate': min((result.get('avg_ypc', 0) or 0) / 10.0, 1.0),
            'explosive_pass_rate': min((result.get('avg_ypa', 0) or 0) / 20.0, 1.0),
            'explosive_play_rate': (result.get('avg_explosive_plays', 0) or 0) / total_plays,
            'big_play_rate': (result.get('avg_big_plays', 0) or 0) / total_plays,
            'scoring_opportunity_rate': (result.get('avg_scoring_opps', 0) or 0) / max(total_plays / 12, 1)
        }

    def _extract_line_movement_features(self, game_id: int) -> Dict:
        """Extract sharp vs public line movement features."""
        # Sharp books
        sharp_books = [1105, 1106, 1118]  # Pinnacle, Circa, BetOnline

        # Public books
        public_books = [1100, 1101, 1103, 1104]  # DraftKings, FanDuel, BetMGM, Caesars

        query = """
            WITH line_history AS (
                SELECT
                    sportsbook_id,
                    spread_home,
                    total_over,
                    moneyline_home,
                    created_at,
                    ROW_NUMBER() OVER (PARTITION BY sportsbook_id ORDER BY created_at ASC) as rn_first,
                    ROW_NUMBER() OVER (PARTITION BY sportsbook_id ORDER BY created_at DESC) as rn_last
                FROM odds
                WHERE game_id = %s
            )
            SELECT
                sportsbook_id,
                MAX(CASE WHEN rn_first = 1 THEN spread_home END) as opening_spread,
                MAX(CASE WHEN rn_last = 1 THEN spread_home END) as current_spread,
                MAX(CASE WHEN rn_first = 1 THEN total_over END) as opening_total,
                MAX(CASE WHEN rn_last = 1 THEN total_over END) as current_total,
                MAX(CASE WHEN rn_first = 1 THEN moneyline_home END) as opening_ml,
                MAX(CASE WHEN rn_last = 1 THEN moneyline_home END) as current_ml
            FROM line_history
            GROUP BY sportsbook_id
        """

        results = self.db.fetch_all(query, (game_id,))

        if not results:
            return {
                'sharp_line_movement': 0.0,
                'public_line_movement': 0.0,
                'line_movement_divergence': 0.0,
                'reverse_line_movement': 0.0,
                'line_movement_magnitude': 0.0,
                'total_movement': 0.0,
                'sharp_total_movement': 0.0,
                'public_total_movement': 0.0
            }

        sharp_movements = []
        public_movements = []
        sharp_total_movements = []
        public_total_movements = []

        for book in results:
            book_id = book['sportsbook_id']

            if book['opening_spread'] is not None and book['current_spread'] is not None:
                movement = book['current_spread'] - book['opening_spread']

                if book_id in sharp_books:
                    sharp_movements.append(movement)
                elif book_id in public_books:
                    public_movements.append(movement)

            if book['opening_total'] is not None and book['current_total'] is not None:
                total_movement = book['current_total'] - book['opening_total']

                if book_id in sharp_books:
                    sharp_total_movements.append(total_movement)
                elif book_id in public_books:
                    public_total_movements.append(total_movement)

        # Calculate features
        features = {
            'sharp_line_movement': np.mean(sharp_movements) if sharp_movements else 0.0,
            'public_line_movement': np.mean(public_movements) if public_movements else 0.0,
            'sharp_total_movement': np.mean(sharp_total_movements) if sharp_total_movements else 0.0,
            'public_total_movement': np.mean(public_total_movements) if public_total_movements else 0.0,
        }

        # Line movement divergence (sharp vs public disagreement)
        if sharp_movements and public_movements:
            features['line_movement_divergence'] = abs(features['sharp_line_movement'] -
                                                      features['public_line_movement'])
        else:
            features['line_movement_divergence'] = 0.0

        # Reverse line movement indicator
        if sharp_movements and public_movements:
            sharp_direction = np.sign(features['sharp_line_movement'])
            public_direction = np.sign(features['public_line_movement'])
            features['reverse_line_movement'] = float(sharp_direction != public_direction and
                                                     abs(features['sharp_line_movement']) > 0.5)
        else:
            features['reverse_line_movement'] = 0.0

        # Line movement magnitude
        all_movements = sharp_movements + public_movements
        features['line_movement_magnitude'] = np.mean([abs(m) for m in all_movements]) if all_movements else 0.0

        # Total movement
        all_total_movements = sharp_total_movements + public_total_movements
        features['total_movement'] = np.mean(all_total_movements) if all_total_movements else 0.0

        return features

    def _calculate_srs(self, team_id: int, season: int, week: int) -> float:
        """
        Calculate Simple Rating System (SRS) for a team.

        SRS = Average Point Differential + Strength of Schedule
        """
        query = """
            WITH team_games AS (
                SELECT
                    CASE WHEN home_team_id = %s THEN margin ELSE -margin END as point_diff,
                    CASE WHEN home_team_id = %s THEN away_team_id ELSE home_team_id END as opponent_id
                FROM games
                WHERE (home_team_id = %s OR away_team_id = %s)
                  AND season = %s
                  AND week < %s
                  AND status IN ('Final', 'F/OT')
            ),
            opponent_records AS (
                SELECT
                    tg.opponent_id,
                    AVG(CASE WHEN g.home_team_id = tg.opponent_id THEN g.margin ELSE -g.margin END) as opp_avg_margin
                FROM team_games tg
                JOIN games g ON (g.home_team_id = tg.opponent_id OR g.away_team_id = tg.opponent_id)
                WHERE g.season = %s
                  AND g.status IN ('Final', 'F/OT')
                GROUP BY tg.opponent_id
            )
            SELECT
                AVG(tg.point_diff) as avg_point_diff,
                AVG(opp.opp_avg_margin) as avg_opp_strength
            FROM team_games tg
            LEFT JOIN opponent_records opp ON tg.opponent_id = opp.opponent_id
        """

        result = self.db.fetch_one(query, (team_id, team_id, team_id, team_id,
                                          season, week, season))

        if result:
            avg_diff = result.get('avg_point_diff', 0) or 0
            avg_opp = result.get('avg_opp_strength', 0) or 0
            return avg_diff + (avg_opp * 0.5)  # Weight opponent strength at 50%

        return 0.0

    def _calculate_strength_of_schedule(self, team_id: int, season: int, week: int) -> float:
        """Calculate strength of schedule based on opponent win percentages."""
        query = """
            WITH team_opponents AS (
                SELECT DISTINCT
                    CASE WHEN home_team_id = %s THEN away_team_id ELSE home_team_id END as opponent_id
                FROM games
                WHERE (home_team_id = %s OR away_team_id = %s)
                  AND season = %s
                  AND week < %s
                  AND status IN ('Final', 'F/OT')
            )
            SELECT
                AVG(COALESCE(tss.wins, 0) / NULLIF((tss.wins + tss.losses), 0)) as avg_opp_win_pct
            FROM team_opponents opp
            LEFT JOIN team_season_stats tss ON opp.opponent_id = tss.team_id AND tss.season = %s
        """

        result = self.db.fetch_one(query, (team_id, team_id, team_id, season, week, season))

        if result:
            return result.get('avg_opp_win_pct', 0.5) or 0.5

        return 0.5

    def _calculate_pace(self, team_stats: Dict) -> float:
        """Calculate pace factor (plays per minute)."""
        plays_per_game = team_stats.get('total_plays', 70) or 70
        time_of_possession = team_stats.get('time_of_possession', 30) or 30

        if time_of_possession > 0:
            return plays_per_game / time_of_possession
        return 2.3  # Average pace

    def _calculate_tempo_factor(self, home_stats: Dict, away_stats: Dict) -> float:
        """Calculate combined tempo factor for the matchup."""
        home_pace = self._calculate_pace(home_stats)
        away_pace = self._calculate_pace(away_stats)

        # Geometric mean for combined tempo
        return np.sqrt(home_pace * away_pace)

    def _extract_havoc_features(self, havoc_stats: Dict, prefix: str = '') -> Dict:
        """Extract havoc-related features."""
        return {
            f'{prefix}tackles_for_loss_rate': havoc_stats.get('tackles_for_loss_rate', 0.0),
            f'{prefix}sacks_per_dropback': havoc_stats.get('sacks_per_dropback', 0.0),
            f'{prefix}turnover_rate': havoc_stats.get('turnover_rate', 0.0),
            f'{prefix}havoc_rate_total': havoc_stats.get('havoc_rate_total', 0.0),
            f'{prefix}pass_breakup_rate': havoc_stats.get('pass_breakup_rate', 0.0),
        }

    def _extract_explosive_features(self, explosive_stats: Dict, prefix: str = '') -> Dict:
        """Extract explosive play features."""
        return {
            f'{prefix}explosive_rush_rate': explosive_stats.get('explosive_rush_rate', 0.0),
            f'{prefix}explosive_pass_rate': explosive_stats.get('explosive_pass_rate', 0.0),
            f'{prefix}explosive_play_rate': explosive_stats.get('explosive_play_rate', 0.0),
            f'{prefix}big_play_rate': explosive_stats.get('big_play_rate', 0.0),
            f'{prefix}scoring_opportunity_rate': explosive_stats.get('scoring_opportunity_rate', 0.0),
        }

    def _extract_opponent_adjusted_features(self, adj_stats: Dict, prefix: str = '') -> Dict:
        """Extract opponent-adjusted features."""
        return {
            f'{prefix}offensive_efficiency': adj_stats.get('offensive_efficiency', 0.0),
            f'{prefix}defensive_efficiency': adj_stats.get('defensive_efficiency', 0.0),
            f'{prefix}epa_per_play': adj_stats.get('epa_per_play', 0.0),
            f'{prefix}success_rate': adj_stats.get('success_rate', 0.0),
        }

    def _extract_adjusted_matchup_features(self, home_adj: Dict, away_adj: Dict) -> Dict:
        """Extract matchup differentials using adjusted stats."""
        return {
            'adj_offensive_diff': (home_adj.get('offensive_efficiency', 0) -
                                  away_adj.get('offensive_efficiency', 0)),
            'adj_defensive_diff': (home_adj.get('defensive_efficiency', 0) -
                                  away_adj.get('defensive_efficiency', 0)),
            'adj_epa_diff': (home_adj.get('epa_per_play', 0) -
                            away_adj.get('epa_per_play', 0)),
            'adj_success_rate_diff': (home_adj.get('success_rate', 0) -
                                     away_adj.get('success_rate', 0)),
        }

    # Inherit other methods from the original FeatureExtractor
    def _get_team_stats(self, team_id: int, season: int) -> Dict:
        """Get team season statistics."""
        query = """
            SELECT * FROM team_season_stats
            WHERE team_id = %s AND season = %s
        """
        result = self.db.fetch_one(query, (team_id, season))
        return result if result else {}

    def _get_recent_form(self, team_id: int, season: int, week: int, n_games: int = 5) -> Dict:
        """Get recent form over last N games."""
        query = """
            SELECT
                AVG(CASE WHEN home_team_id = %s THEN home_score ELSE away_score END) as avg_score,
                AVG(CASE WHEN home_team_id = %s THEN away_score ELSE home_score END) as avg_opp_score,
                AVG(CASE WHEN home_team_id = %s THEN margin ELSE -margin END) as avg_margin,
                COUNT(CASE WHEN (home_team_id = %s AND margin > 0) OR
                          (away_team_id = %s AND margin < 0) THEN 1 END) as wins
            FROM (
                SELECT * FROM games
                WHERE (home_team_id = %s OR away_team_id = %s)
                  AND season = %s
                  AND week < %s
                  AND status IN ('Final', 'F/OT')
                ORDER BY week DESC
                LIMIT %s
            ) recent_games
        """
        result = self.db.fetch_one(query, (team_id, team_id, team_id, team_id, team_id,
                                          team_id, team_id, season, week, n_games))
        return result if result else {}

    def _get_home_away_splits(self, team_id: int, season: int, week: int, is_home: bool) -> Dict:
        """Get home/away split statistics."""
        if is_home:
            query = """
                SELECT
                    AVG(home_score) as avg_score,
                    AVG(away_score) as avg_opp_score,
                    AVG(margin) as avg_margin
                FROM games
                WHERE home_team_id = %s
                  AND season = %s
                  AND week < %s
                  AND status IN ('Final', 'F/OT')
            """
        else:
            query = """
                SELECT
                    AVG(away_score) as avg_score,
                    AVG(home_score) as avg_opp_score,
                    AVG(-margin) as avg_margin
                FROM games
                WHERE away_team_id = %s
                  AND season = %s
                  AND week < %s
                  AND status IN ('Final', 'F/OT')
            """

        result = self.db.fetch_one(query, (team_id, season, week))
        return result if result else {}

    def _get_talent_composite(self, team_id: int) -> float:
        """Get team talent composite (recruiting rankings)."""
        # This would typically come from a recruiting database
        # For now, return a normalized value based on team prestige
        query = """
            SELECT
                AVG(CASE WHEN home_team_id = %s THEN margin ELSE -margin END) as historical_margin
            FROM games
            WHERE (home_team_id = %s OR away_team_id = %s)
              AND status IN ('Final', 'F/OT')
        """
        result = self.db.fetch_one(query, (team_id, team_id, team_id))

        if result:
            # Normalize to 0-100 scale
            margin = result.get('historical_margin', 0) or 0
            return min(max(50 + margin * 2, 0), 100)
        return 50.0

    def _extract_efficiency_features(self, stats: Dict, prefix: str = '') -> Dict:
        """Extract efficiency features from team stats."""
        features = {}
        features[f'{prefix}offensive_efficiency'] = stats.get('yards_per_game', 0) or 0.0
        features[f'{prefix}defensive_efficiency'] = stats.get('yards_allowed_per_game', 0) or 0.0
        features[f'{prefix}third_down_pct'] = stats.get('third_down_conversion_pct', 0) or 0.0
        features[f'{prefix}red_zone_pct'] = stats.get('red_zone_scoring_pct', 0) or 0.0
        features[f'{prefix}points_per_game'] = stats.get('points_per_game', 0) or 0.0
        features[f'{prefix}points_allowed'] = stats.get('points_allowed_per_game', 0) or 0.0
        features[f'{prefix}turnover_margin'] = (stats.get('takeaways', 0) or 0) - (stats.get('turnovers', 0) or 0)
        return features

    def _extract_qb_features(self, stats: Dict, prefix: str = '') -> Dict:
        """Extract quarterback features."""
        features = {}
        features[f'{prefix}qb_rating'] = stats.get('qb_rating', 0) or 0.0
        features[f'{prefix}completion_pct'] = stats.get('completion_pct', 0) or 0.0
        features[f'{prefix}pass_td_rate'] = stats.get('pass_td_rate', 0) or 0.0
        features[f'{prefix}int_rate'] = stats.get('int_rate', 0) or 0.0
        features[f'{prefix}yards_per_attempt'] = stats.get('yards_per_attempt', 0) or 0.0
        return features

    def _extract_recent_form_features(self, recent: Dict, prefix: str = '') -> Dict:
        """Extract recent form features."""
        features = {}
        features[f'{prefix}recent_ppg'] = recent.get('avg_score', 0) or 0.0
        features[f'{prefix}recent_margin'] = recent.get('avg_margin', 0) or 0.0
        features[f'{prefix}recent_wins'] = recent.get('wins', 0) or 0.0
        features[f'{prefix}recent_opp_ppg'] = recent.get('avg_opp_score', 0) or 0.0
        return features

    def _extract_split_features(self, splits: Dict, prefix: str = '') -> Dict:
        """Extract home/away split features."""
        features = {}
        features[f'{prefix}split_ppg'] = splits.get('avg_score', 0) or 0.0
        features[f'{prefix}split_margin'] = splits.get('avg_margin', 0) or 0.0
        features[f'{prefix}split_opp_ppg'] = splits.get('avg_opp_score', 0) or 0.0
        return features

    def _extract_matchup_features(self, home_stats: Dict, away_stats: Dict) -> Dict:
        """Extract basic matchup differential features."""
        features = {}

        # Offensive vs Defensive matchups
        features['offensive_diff'] = ((home_stats.get('yards_per_game', 0) or 0) -
                                     (away_stats.get('yards_per_game', 0) or 0))
        features['defensive_diff'] = ((home_stats.get('yards_allowed_per_game', 0) or 0) -
                                     (away_stats.get('yards_allowed_per_game', 0) or 0))

        # Scoring differentials
        features['ppg_diff'] = ((home_stats.get('points_per_game', 0) or 0) -
                               (away_stats.get('points_per_game', 0) or 0))
        features['def_ppg_diff'] = ((home_stats.get('points_allowed_per_game', 0) or 0) -
                                   (away_stats.get('points_allowed_per_game', 0) or 0))

        # Turnover differential
        home_to_margin = ((home_stats.get('takeaways', 0) or 0) -
                         (home_stats.get('turnovers', 0) or 0))
        away_to_margin = ((away_stats.get('takeaways', 0) or 0) -
                         (away_stats.get('turnovers', 0) or 0))
        features['turnover_diff'] = home_to_margin - away_to_margin

        return features