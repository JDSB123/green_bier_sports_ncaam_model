"""
NCAA Basketball Elo Rating System.

A proven rating system based on FiveThirtyEight's methodology.
Complements Barttorvik efficiency metrics with game-by-game updates.

WHY ELO:
- Captures recent form that season-aggregate stats miss
- Proven over decades in chess, NFL, NBA, NCAAB
- Simple, interpretable, backtestable
- Handles strength of schedule automatically

METHODOLOGY:
- Start of season: Regress to mean (1500) by 1/3
- K-factor: 20 (standard for college basketball)
- Margin of victory multiplier included
- Home court advantage: ~100 Elo points (~3.5 point spread)

CONVERSION:
- Elo difference to spread: spread = elo_diff / 28.5
- 100 Elo points ≈ 3.5 point spread
- 400 Elo points ≈ 14 point spread (75% win probability)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import math


@dataclass
class EloRating:
    """Elo rating for a team at a point in time."""
    team: str
    rating: float = 1500.0
    games_played: int = 0
    last_updated: datetime | None = None

    def win_probability(self, opponent_elo: float, home_advantage: float = 0) -> float:
        """Calculate win probability against opponent."""
        elo_diff = self.rating - opponent_elo + home_advantage
        return 1.0 / (1.0 + 10 ** (-elo_diff / 400))

    def to_spread(self, opponent_elo: float, home_advantage: float = 0) -> float:
        """Convert Elo difference to predicted spread (negative = favored)."""
        elo_diff = self.rating - opponent_elo + home_advantage
        # 28.5 Elo points ≈ 1 point of spread
        return -elo_diff / 28.5


class EloSystem:
    """
    NCAA Basketball Elo Rating System.

    Based on FiveThirtyEight's proven methodology with adjustments
    for college basketball's unique characteristics.
    """

    # Configuration
    INITIAL_RATING = 1500.0
    K_FACTOR = 20.0  # How much ratings change per game
    HOME_ADVANTAGE = 100.0  # ~3.5 points of spread

    # Season regression: teams regress 1/3 toward mean
    SEASON_REGRESSION = 1/3

    # Margin of victory multiplier
    # Prevents blowouts from over-weighting
    MOV_MULTIPLIER = 0.75  # Dampening factor for margin

    def __init__(self):
        """Initialize Elo system."""
        self.ratings: dict[str, EloRating] = {}
        self._initialized_teams: set[str] = set()

    def get_rating(self, team: str) -> EloRating:
        """Get or create rating for a team."""
        if team not in self.ratings:
            self.ratings[team] = EloRating(team=team, rating=self.INITIAL_RATING)
        return self.ratings[team]

    def new_season(self):
        """Regress all ratings toward mean for new season."""
        for team, rating in self.ratings.items():
            # Regress 1/3 toward mean
            new_rating = rating.rating + self.SEASON_REGRESSION * (self.INITIAL_RATING - rating.rating)
            self.ratings[team] = EloRating(
                team=team,
                rating=new_rating,
                games_played=0,
                last_updated=rating.last_updated
            )

    def predict(
        self,
        home_team: str,
        away_team: str,
        is_neutral: bool = False
    ) -> dict:
        """
        Predict game outcome using Elo ratings.

        Args:
            home_team: Home team name
            away_team: Away team name
            is_neutral: True if neutral site

        Returns:
            Dict with predicted spread, win probability, and confidence
        """
        home_elo = self.get_rating(home_team)
        away_elo = self.get_rating(away_team)

        hca = 0 if is_neutral else self.HOME_ADVANTAGE

        # Win probability
        home_win_prob = home_elo.win_probability(away_elo.rating, hca)

        # Predicted spread (negative = home favored)
        spread = home_elo.to_spread(away_elo.rating, hca)

        # Confidence based on games played (more games = more confidence)
        min_games = min(home_elo.games_played, away_elo.games_played)
        confidence = min(1.0, min_games / 10)  # Max confidence after 10 games

        return {
            "home_team": home_team,
            "away_team": away_team,
            "home_elo": round(home_elo.rating, 1),
            "away_elo": round(away_elo.rating, 1),
            "elo_diff": round(home_elo.rating - away_elo.rating + hca, 1),
            "predicted_spread": round(spread, 1),
            "home_win_prob": round(home_win_prob, 3),
            "confidence": round(confidence, 2),
            "home_games_played": home_elo.games_played,
            "away_games_played": away_elo.games_played,
        }

    def update_from_game(
        self,
        home_team: str,
        away_team: str,
        home_score: int,
        away_score: int,
        is_neutral: bool = False,
        game_date: datetime | None = None
    ) -> dict:
        """
        Update Elo ratings after a game result.

        Args:
            home_team: Home team name
            away_team: Away team name
            home_score: Home team final score
            away_score: Away team final score
            is_neutral: True if neutral site
            game_date: Date of game

        Returns:
            Dict with old and new ratings
        """
        home_elo = self.get_rating(home_team)
        away_elo = self.get_rating(away_team)

        hca = 0 if is_neutral else self.HOME_ADVANTAGE

        # Expected outcomes
        home_expected = home_elo.win_probability(away_elo.rating, hca)
        away_expected = 1 - home_expected

        # Actual outcomes (1 = win, 0 = loss, 0.5 = tie)
        margin = home_score - away_score
        if margin > 0:
            home_actual, away_actual = 1.0, 0.0
        elif margin < 0:
            home_actual, away_actual = 0.0, 1.0
        else:
            home_actual, away_actual = 0.5, 0.5

        # Margin of victory multiplier
        # Prevents blowouts from over-weighting
        abs_margin = abs(margin)
        mov_mult = math.log(abs_margin + 1) * self.MOV_MULTIPLIER
        mov_mult = min(mov_mult, 2.0)  # Cap at 2x

        # Calculate rating changes
        home_change = self.K_FACTOR * mov_mult * (home_actual - home_expected)
        away_change = self.K_FACTOR * mov_mult * (away_actual - away_expected)

        # Store old ratings
        old_home = home_elo.rating
        old_away = away_elo.rating

        # Update ratings
        self.ratings[home_team] = EloRating(
            team=home_team,
            rating=home_elo.rating + home_change,
            games_played=home_elo.games_played + 1,
            last_updated=game_date or datetime.now()
        )
        self.ratings[away_team] = EloRating(
            team=away_team,
            rating=away_elo.rating + away_change,
            games_played=away_elo.games_played + 1,
            last_updated=game_date or datetime.now()
        )

        return {
            "home_team": home_team,
            "away_team": away_team,
            "home_score": home_score,
            "away_score": away_score,
            "margin": margin,
            "home_old_elo": round(old_home, 1),
            "home_new_elo": round(self.ratings[home_team].rating, 1),
            "home_change": round(home_change, 1),
            "away_old_elo": round(old_away, 1),
            "away_new_elo": round(self.ratings[away_team].rating, 1),
            "away_change": round(away_change, 1),
        }

    def initialize_from_barttorvik(self, team: str, barthag: float, adj_o: float, adj_d: float):
        """
        Initialize team Elo from Barttorvik ratings.

        Converts Barttorvik efficiency metrics to Elo scale.
        This gives a better starting point than flat 1500.

        Args:
            team: Team name
            barthag: Barttorvik's expected win probability (0-1)
            adj_o: Adjusted offensive efficiency
            adj_d: Adjusted defensive efficiency
        """
        # Convert barthag (0-1) to Elo scale
        # barthag of 0.5 = 1500 Elo (average)
        # barthag of 0.9 = ~1700 Elo (elite)
        # barthag of 0.1 = ~1300 Elo (weak)

        if barthag <= 0:
            barthag = 0.01
        if barthag >= 1:
            barthag = 0.99

        # Inverse of win probability formula
        # barthag = 1 / (1 + 10^(-elo_diff/400))
        # Solve for elo_diff when opponent is average (1500)
        elo_vs_average = -400 * math.log10((1 / barthag) - 1)
        initial_elo = self.INITIAL_RATING + elo_vs_average

        # Clamp to reasonable range
        initial_elo = max(1200, min(1800, initial_elo))

        self.ratings[team] = EloRating(
            team=team,
            rating=initial_elo,
            games_played=0,
            last_updated=datetime.now()
        )

        return initial_elo

    def get_all_ratings(self) -> list[dict]:
        """Get all team ratings sorted by rating."""
        return sorted(
            [
                {
                    "team": team,
                    "rating": round(rating.rating, 1),
                    "games_played": rating.games_played,
                }
                for team, rating in self.ratings.items()
            ],
            key=lambda x: x["rating"],
            reverse=True
        )


# Singleton instance
elo_system = EloSystem()


def barttorvik_spread(
    home_adj_o: float,
    home_adj_d: float,
    away_adj_o: float,
    away_adj_d: float,
    home_tempo: float,
    away_tempo: float,
    is_neutral: bool = False,
    hca: float = 3.5
) -> float:
    """
    Calculate spread using Barttorvik's proven formula.

    This is the BASELINE approach we should be using.

    Formula:
        home_pts = tempo * (home_adj_o + away_adj_d) / 200
        away_pts = tempo * (away_adj_o + home_adj_d) / 200
        spread = -(home_pts - away_pts + HCA)
    """
    avg_tempo = (home_tempo + away_tempo) / 2

    # Expected efficiency (per 100 possessions)
    home_eff = (home_adj_o + away_adj_d) / 2
    away_eff = (away_adj_o + home_adj_d) / 2

    # Expected scores
    home_pts = avg_tempo * home_eff / 100
    away_pts = avg_tempo * away_eff / 100

    # Margin
    margin = home_pts - away_pts

    # Apply HCA
    actual_hca = 0 if is_neutral else hca

    # Spread (negative = home favored)
    spread = -(margin + actual_hca)

    return round(spread, 1)


def barttorvik_total(
    home_adj_o: float,
    home_adj_d: float,
    away_adj_o: float,
    away_adj_d: float,
    home_tempo: float,
    away_tempo: float
) -> float:
    """
    Calculate total using Barttorvik's proven formula.

    This is the BASELINE approach for totals.

    Formula:
        total = tempo * (home_eff + away_eff) / 100
    """
    avg_tempo = (home_tempo + away_tempo) / 2

    # Combined efficiency
    home_eff = (home_adj_o + away_adj_d) / 2
    away_eff = (away_adj_o + home_adj_d) / 2

    # Total
    total = avg_tempo * (home_eff + away_eff) / 100

    return round(total, 1)
