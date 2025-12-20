"""
Green Bier Sport Ventures - NCAAM Prediction Engine v6.0

ENHANCED MODEL with 6 Independent Markets:
  1. Full Game Spread
  2. Full Game Total
  3. Full Game Moneyline
  4. First Half Spread
  5. First Half Total
  6. First Half Moneyline

KEY DIFFERENCES from v5.0:
  - Each market uses INDEPENDENT calculations (not inferred from others)
  - Incorporates Four Factors for matchup-specific adjustments
  - Uses Barttorvik's extended metrics (EFG, TOR, ORB, FTR, 3PR)
  - Variance-adjusted win probabilities based on team shooting profiles
  - First Half models are NOT derived from Full Game

Matchup Adjustments:
  - Rebounding Edge: ORB vs DRB differential
  - Turnover Battle: TOR vs TORD differential
  - Pace Mismatch: Tempo differential affects variance
  - Shooting Style: 3PR affects variance estimation
"""

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple
from uuid import UUID

from app.config import settings
from app.models import (
    BetTier,
    BetType,
    BettingRecommendation,
    MarketOdds,
    Pick,
    Prediction,
    TeamRatings,
)


@dataclass
class ExtendedTeamRatings:
    """Extended team ratings including Four Factors."""
    # Core ratings (from v5.0)
    team_name: str
    adj_o: float
    adj_d: float
    tempo: float
    rank: int

    # Four Factors - Shooting
    efg: Optional[float] = None      # Effective FG%
    efgd: Optional[float] = None     # Effective FG% Defense

    # Four Factors - Turnovers
    tor: Optional[float] = None      # Turnover Rate
    tord: Optional[float] = None     # Turnover Rate Defense

    # Four Factors - Rebounding
    orb: Optional[float] = None      # Offensive Rebound Rate
    drb: Optional[float] = None      # Defensive Rebound Rate

    # Four Factors - Free Throws
    ftr: Optional[float] = None      # Free Throw Rate
    ftrd: Optional[float] = None     # Free Throw Rate Defense

    # Shooting Profile
    three_pt_rate: Optional[float] = None   # 3-Point Attempt Rate
    three_pt_rate_d: Optional[float] = None

    # Quality Metrics
    barthag: Optional[float] = None  # Expected win % vs average D1 team
    wab: Optional[float] = None      # Wins Above Bubble

    @property
    def net_rating(self) -> float:
        """Net efficiency rating."""
        return self.adj_o - self.adj_d

    @property
    def has_four_factors(self) -> bool:
        """Check if Four Factors data is available."""
        return all([
            self.efg is not None,
            self.tor is not None,
            self.orb is not None,
            self.ftr is not None
        ])


@dataclass
class MarketPrediction:
    """Prediction for a single market."""
    predicted_line: float
    confidence: float
    variance: float
    win_prob: Optional[float] = None  # For spread/ML markets


@dataclass
class FullPredictionOutput:
    """Complete prediction output for all 6 markets."""
    # Full Game
    spread: MarketPrediction
    total: MarketPrediction
    moneyline: Tuple[MarketPrediction, MarketPrediction]  # (home, away)

    # First Half
    spread_1h: MarketPrediction
    total_1h: MarketPrediction
    moneyline_1h: Tuple[MarketPrediction, MarketPrediction]

    # Derived values
    home_score: float
    away_score: float
    home_score_1h: float
    away_score_1h: float


class EnhancedPredictor:
    """
    Enhanced predictor with 6 independent market models.

    Each market uses its own optimized formula and doesn't rely on
    inference from other markets.
    """

    def __init__(self):
        self.config = settings.model

        # Market-specific HCA values (separately optimized)
        self.hca = {
            "spread_fg": 3.0,      # Full game spread
            "spread_1h": 1.5,      # First half spread (NOT derived from FG)
            "total_fg": 0.9,       # Full game total adjustment
            "total_1h": 0.45,      # First half total (NOT derived from FG)
        }

        # Variance parameters
        self.base_sigma = 11.0    # Base spread-to-prob sigma
        self.pace_variance_factor = 0.1
        self.three_pt_variance_factor = 0.15

    def predict(
        self,
        home: ExtendedTeamRatings,
        away: ExtendedTeamRatings,
        is_neutral: bool = False,
    ) -> FullPredictionOutput:
        """
        Generate independent predictions for all 6 markets.

        Args:
            home: Extended ratings for home team
            away: Extended ratings for away team
            is_neutral: True if neutral site game

        Returns:
            Complete predictions for all markets
        """
        # ═══════════════════════════════════════════════════════════════════════
        # MATCHUP ADJUSTMENTS (applied to efficiency calculations)
        # ═══════════════════════════════════════════════════════════════════════

        orb_adj, tor_adj = self._calculate_matchup_adjustments(home, away)

        # ═══════════════════════════════════════════════════════════════════════
        # FULL GAME PREDICTIONS (independent calculations)
        # ═══════════════════════════════════════════════════════════════════════

        fg_spread, fg_total, home_score, away_score = self._predict_full_game(
            home, away, is_neutral, orb_adj, tor_adj
        )

        # ═══════════════════════════════════════════════════════════════════════
        # FIRST HALF PREDICTIONS (independent, NOT derived from full game)
        # ═══════════════════════════════════════════════════════════════════════

        h1_spread, h1_total, home_score_1h, away_score_1h = self._predict_first_half(
            home, away, is_neutral, orb_adj, tor_adj
        )

        # ═══════════════════════════════════════════════════════════════════════
        # MONEYLINE CALCULATIONS (from spreads with variance adjustment)
        # ═══════════════════════════════════════════════════════════════════════

        game_variance = self._calculate_game_variance(home, away)

        fg_ml = self._calculate_moneyline(fg_spread, game_variance)
        h1_ml = self._calculate_moneyline(h1_spread, game_variance * 1.1)  # 1H has higher variance

        return FullPredictionOutput(
            spread=fg_spread,
            total=fg_total,
            moneyline=fg_ml,
            spread_1h=h1_spread,
            total_1h=h1_total,
            moneyline_1h=h1_ml,
            home_score=home_score,
            away_score=away_score,
            home_score_1h=home_score_1h,
            away_score_1h=away_score_1h,
        )

    def _calculate_matchup_adjustments(
        self,
        home: ExtendedTeamRatings,
        away: ExtendedTeamRatings
    ) -> Tuple[float, float]:
        """
        Calculate matchup-specific adjustments based on Four Factors.

        Returns:
            Tuple of (rebounding_adjustment, turnover_adjustment)
        """
        orb_adj = 0.0
        tor_adj = 0.0

        # Rebounding edge: Home team's ORB vs Away's DRB
        if home.orb is not None and away.drb is not None:
            # Higher ORB vs lower opponent DRB = more second chance points
            # Average ORB is ~28%, average DRB is ~72%
            home_orb_edge = (home.orb - 28) - (72 - away.drb)
            orb_adj += home_orb_edge * 0.15  # ~0.15 points per % of edge

        if away.orb is not None and home.drb is not None:
            away_orb_edge = (away.orb - 28) - (72 - home.drb)
            orb_adj -= away_orb_edge * 0.15

        # Turnover differential: Away's TORD vs Home's TOR
        if home.tor is not None and away.tord is not None:
            # Lower TOR vs lower opponent TORD = fewer turnovers = advantage
            home_tor_edge = (away.tord - 20) - (home.tor - 20)
            tor_adj += home_tor_edge * 0.10  # ~0.10 points per % of edge

        if away.tor is not None and home.tord is not None:
            away_tor_edge = (home.tord - 20) - (away.tor - 20)
            tor_adj -= away_tor_edge * 0.10

        return orb_adj, tor_adj

    def _predict_full_game(
        self,
        home: ExtendedTeamRatings,
        away: ExtendedTeamRatings,
        is_neutral: bool,
        orb_adj: float,
        tor_adj: float
    ) -> Tuple[MarketPrediction, MarketPrediction, float, float]:
        """
        Generate full game spread and total predictions.

        Uses standard Barttorvik efficiency model with matchup adjustments.
        """
        avg_tempo = (home.tempo + away.tempo) / 2

        # Base efficiency calculations
        home_expected_eff = (home.adj_o * away.adj_d) / 100.0
        away_expected_eff = (away.adj_o * home.adj_d) / 100.0

        # Apply matchup adjustments to efficiency
        home_expected_eff += orb_adj + tor_adj
        away_expected_eff -= orb_adj + tor_adj

        # Base scores
        home_score_base = home_expected_eff * avg_tempo / 100.0
        away_score_base = away_expected_eff * avg_tempo / 100.0

        # HCA for spread
        hca_spread = 0.0 if is_neutral else self.hca["spread_fg"]
        spread = -((home_score_base - away_score_base) + hca_spread)

        # HCA for total (minimal impact)
        hca_total = 0.0 if is_neutral else self.hca["total_fg"]
        total = home_score_base + away_score_base + hca_total

        # Final scores
        home_score = (total - spread) / 2
        away_score = (total + spread) / 2

        # Calculate confidence based on data quality
        spread_confidence = self._calculate_confidence(home, away, "spread")
        total_confidence = self._calculate_confidence(home, away, "total")

        # Calculate variance
        variance = self._calculate_game_variance(home, away)

        # Win probability from spread
        win_prob = self._spread_to_win_prob(spread, variance)

        spread_pred = MarketPrediction(
            predicted_line=round(spread, 1),
            confidence=spread_confidence,
            variance=variance,
            win_prob=win_prob
        )

        total_pred = MarketPrediction(
            predicted_line=round(total, 1),
            confidence=total_confidence,
            variance=variance * 0.8  # Total variance slightly lower
        )

        return spread_pred, total_pred, round(home_score, 1), round(away_score, 1)

    def _predict_first_half(
        self,
        home: ExtendedTeamRatings,
        away: ExtendedTeamRatings,
        is_neutral: bool,
        orb_adj: float,
        tor_adj: float
    ) -> Tuple[MarketPrediction, MarketPrediction, float, float]:
        """
        Generate first half predictions INDEPENDENTLY (not derived from full game).

        First half has different dynamics:
          - Less time for regression to mean
          - Coaching adjustments haven't happened
          - Starters play more minutes (less bench variance)
          - HCA effect is slightly different
        """
        # Use 48% of tempo for first half (slightly less than 50%)
        # This accounts for longer possessions in first half
        avg_tempo = (home.tempo + away.tempo) / 2
        h1_tempo = avg_tempo * 0.48

        # Efficiency in first half (slightly different than full game)
        # Teams tend to be more conservative early
        h1_eff_factor = 0.98  # Slightly lower efficiency in 1H

        home_expected_eff = (home.adj_o * away.adj_d) / 100.0 * h1_eff_factor
        away_expected_eff = (away.adj_o * home.adj_d) / 100.0 * h1_eff_factor

        # Apply reduced matchup adjustments (less time for factors to manifest)
        home_expected_eff += (orb_adj + tor_adj) * 0.8
        away_expected_eff -= (orb_adj + tor_adj) * 0.8

        # First half base scores
        home_score_1h = home_expected_eff * h1_tempo / 100.0
        away_score_1h = away_expected_eff * h1_tempo / 100.0

        # First half HCA (independently optimized, NOT derived from FG)
        hca_spread_1h = 0.0 if is_neutral else self.hca["spread_1h"]
        hca_total_1h = 0.0 if is_neutral else self.hca["total_1h"]

        # First half spread
        spread_1h = -((home_score_1h - away_score_1h) + hca_spread_1h)

        # First half total
        total_1h = home_score_1h + away_score_1h + hca_total_1h

        # Confidence is slightly lower for 1H (more variance)
        spread_confidence = self._calculate_confidence(home, away, "spread") * 0.92
        total_confidence = self._calculate_confidence(home, away, "total") * 0.92

        # Variance is higher for 1H
        variance = self._calculate_game_variance(home, away) * 1.15

        # Win probability
        win_prob = self._spread_to_win_prob(spread_1h, variance)

        spread_pred = MarketPrediction(
            predicted_line=round(spread_1h, 1),
            confidence=spread_confidence,
            variance=variance,
            win_prob=win_prob
        )

        total_pred = MarketPrediction(
            predicted_line=round(total_1h, 1),
            confidence=total_confidence,
            variance=variance * 0.85
        )

        return spread_pred, total_pred, round(home_score_1h, 1), round(away_score_1h, 1)

    def _calculate_game_variance(
        self,
        home: ExtendedTeamRatings,
        away: ExtendedTeamRatings
    ) -> float:
        """
        Calculate expected game variance based on team profiles.

        Higher variance for:
          - High 3-point rate teams (more volatile scoring)
          - Large pace mismatches (uncertain tempo)
          - Teams with extreme styles
        """
        base_variance = self.base_sigma

        # 3-point variance adjustment
        home_3pr = home.three_pt_rate if home.three_pt_rate else 35.0
        away_3pr = away.three_pt_rate if away.three_pt_rate else 35.0
        avg_3pr = (home_3pr + away_3pr) / 2

        # Higher 3PR = more variance (avg is ~35%)
        three_pt_adj = (avg_3pr - 35.0) * self.three_pt_variance_factor

        # Pace mismatch variance
        tempo_diff = abs(home.tempo - away.tempo)
        pace_adj = tempo_diff * self.pace_variance_factor

        return base_variance + three_pt_adj + pace_adj

    def _calculate_confidence(
        self,
        home: ExtendedTeamRatings,
        away: ExtendedTeamRatings,
        market: str
    ) -> float:
        """
        Calculate prediction confidence based on data quality.
        """
        base_confidence = 0.70

        # Rank factor (better teams = more data)
        rank_factor = 1.0 - (min(home.rank, away.rank) / 400)
        base_confidence += rank_factor * 0.10

        # Net rating differential (larger gap = more confident)
        net_diff = abs(home.net_rating - away.net_rating)
        if net_diff > 15:
            base_confidence += 0.10
        elif net_diff > 10:
            base_confidence += 0.05

        # Four Factors bonus (more data = more confident)
        if home.has_four_factors and away.has_four_factors:
            base_confidence += 0.05

        return min(0.95, base_confidence)

    def _spread_to_win_prob(self, spread: float, variance: float) -> float:
        """
        Convert spread to win probability using adjusted normal CDF.

        Args:
            spread: Predicted spread (negative = home favored)
            variance: Game-specific variance (sigma)
        """
        z = -spread / variance
        prob = 0.5 * (1 + math.erf(z / math.sqrt(2)))
        return max(0.01, min(0.99, prob))

    def _calculate_moneyline(
        self,
        spread_pred: MarketPrediction,
        variance: float
    ) -> Tuple[MarketPrediction, MarketPrediction]:
        """
        Calculate moneyline predictions from spread.
        """
        home_prob = self._spread_to_win_prob(spread_pred.predicted_line, variance)
        away_prob = 1 - home_prob

        home_ml = self._prob_to_american_odds(home_prob)
        away_ml = self._prob_to_american_odds(away_prob)

        home_pred = MarketPrediction(
            predicted_line=float(home_ml),
            confidence=spread_pred.confidence,
            variance=variance,
            win_prob=home_prob
        )

        away_pred = MarketPrediction(
            predicted_line=float(away_ml),
            confidence=spread_pred.confidence,
            variance=variance,
            win_prob=away_prob
        )

        return home_pred, away_pred

    def _prob_to_american_odds(self, prob: float) -> int:
        """Convert probability to American odds."""
        if prob >= 0.5:
            return int(-100 * prob / (1 - prob))
        else:
            return int(100 * (1 - prob) / prob)


# Singleton instance
enhanced_predictor = EnhancedPredictor()


def convert_to_extended_ratings(basic: TeamRatings, db_row=None) -> ExtendedTeamRatings:
    """
    Convert basic TeamRatings to ExtendedTeamRatings.

    If db_row is provided (with Four Factors), use that data.
    """
    return ExtendedTeamRatings(
        team_name=basic.team_name,
        adj_o=basic.adj_o,
        adj_d=basic.adj_d,
        tempo=basic.tempo,
        rank=basic.rank,
        # Four Factors (from db_row if available)
        efg=getattr(db_row, 'efg', None) if db_row else None,
        efgd=getattr(db_row, 'efgd', None) if db_row else None,
        tor=getattr(db_row, 'tor', None) if db_row else None,
        tord=getattr(db_row, 'tord', None) if db_row else None,
        orb=getattr(db_row, 'orb', None) if db_row else None,
        drb=getattr(db_row, 'drb', None) if db_row else None,
        ftr=getattr(db_row, 'ftr', None) if db_row else None,
        ftrd=getattr(db_row, 'ftrd', None) if db_row else None,
        three_pt_rate=getattr(db_row, 'three_pt_rate', None) if db_row else None,
        three_pt_rate_d=getattr(db_row, 'three_pt_rate_d', None) if db_row else None,
        barthag=getattr(db_row, 'barthag', None) if db_row else None,
        wab=getattr(db_row, 'wab', None) if db_row else None,
    )
