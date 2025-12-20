"""
NCAA Basketball Prediction Engine v5.1 - MODULAR

SINGLE SOURCE OF TRUTH: All predictions flow through this containerized service.

MODULAR HCA Approach:
- Full Game Spreads: HCA=3.0 (optimized for 16.57% ROI)
- Full Game Totals: HCA=4.5 * 0.2 = 0.9 points (optimized for 34.10% ROI)
- First Half Spreads: HCA=1.5 (50% of full game)
- First Half Totals: HCA=2.25 * 0.1 = 0.225 points (minimal impact)

Core Formula (PROVEN MODEL):
- Base scores: (AdjO * Opponent_AdjD / 100) / 100 * Avg_Tempo
- Full Game Spread: -(home_score_base - away_score_base + HCA_spread)
- Full Game Total: home_score_base + away_score_base + (HCA_total * 0.2)
- First Half: Derived from base scores using pace/score factors
- Moneylines: Converted from spreads using normal CDF (sigma=11)

All 6 markets calculated:
1. Full Game Spread
2. Full Game Total
3. Full Game Moneyline
4. First Half Spread
5. First Half Total
6. First Half Moneyline
"""

import math
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
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
class PredictorOutput:
    """Raw predictor output before market comparison."""
    spread: float
    total: float
    home_score: float
    away_score: float
    spread_1h: float
    total_1h: float
    home_score_1h: float
    away_score_1h: float
    home_win_prob: float
    home_win_prob_1h: float
    home_ml: int
    away_ml: int
    home_ml_1h: int
    away_ml_1h: int


class BarttorkvikPredictor:
    """
    Simplified Barttorvik efficiency-based predictor.

    Core Formula:
        Spread = Home_NetRtg - Away_NetRtg + HCA

    Where:
        NetRtg = AdjO - AdjD

    This is the fundamental efficiency model. No interaction terms,
    no mismatch amplification - just clean, interpretable math.
    """

    def __init__(self):
        self.config = settings.model
        # MODULAR HCA - loaded from config.py (single source of truth)
        # Optimized 2024-12-17: Spreads=3.0 (16.57% ROI), Totals with HCA=4.5 (34.10% ROI)
        self.hca_spread = self.config.home_court_advantage_spread
        self.hca_total = self.config.home_court_advantage_total
        self.hca_spread_1h = self.config.home_court_advantage_spread_1h
        self.hca_total_1h = self.config.home_court_advantage_total_1h

    def predict(
        self,
        home_ratings: TeamRatings,
        away_ratings: TeamRatings,
        is_neutral: bool = False,
    ) -> PredictorOutput:
        """
        Generate predictions for a matchup.

        Args:
            home_ratings: Barttorvik ratings for home team
            away_ratings: Barttorvik ratings for away team
            is_neutral: True if neutral site game

        Returns:
            PredictorOutput with all predictions
        """
        # ─────────────────────────────────────────────────────────────────────
        # SCORE PREDICTIONS - STANDARD BARTTORVIK FORMULA
        # ─────────────────────────────────────────────────────────────────────
        #
        # Standard efficiency formula (proven in backtesting):
        #   Expected points = (Team_AdjO * Opp_AdjD / 100) * Tempo / 100
        #
        # The /100 values are MATHEMATICAL CONSTANTS, not D1 average corrections.
        # Barttorvik ratings are internally consistent - use them as-is.
        #
        avg_tempo = (home_ratings.tempo + away_ratings.tempo) / 2

        # Expected points per 100 possessions for each team
        home_expected_eff = (home_ratings.adj_o * away_ratings.adj_d) / 100.0
        away_expected_eff = (away_ratings.adj_o * home_ratings.adj_d) / 100.0

        # Base scores: efficiency * (tempo / 100)
        home_score_base = home_expected_eff * avg_tempo / 100.0
        away_score_base = away_expected_eff * avg_tempo / 100.0


        # ─────────────────────────────────────────────────────────────────────
        # MODULAR: Calculate spread with spread-specific HCA
        # ─────────────────────────────────────────────────────────────────────
        hca_for_spread = 0.0 if is_neutral else self.hca_spread
        spread = -((home_score_base - away_score_base) + hca_for_spread)

        # ─────────────────────────────────────────────────────────────────────
        # MODULAR: Calculate total with total-specific HCA
        # ─────────────────────────────────────────────────────────────────────
        # PROVEN MODEL: Uses 20% of HCA_total (4.5 * 0.2 = 0.9 points)
        # This formula produced 34.10% ROI in backtesting
        # The 0.2 multiplier accounts for minimal home court impact on pace/scoring
        hca_for_total = 0.0 if is_neutral else self.hca_total
        total = home_score_base + away_score_base + (hca_for_total * 0.2)


        # Derive final scores from spread and total
        home_score = (total - spread) / 2
        away_score = (total + spread) / 2

        # ─────────────────────────────────────────────────────────────────────
        # FIRST HALF PREDICTIONS (MODULAR)
        # ─────────────────────────────────────────────────────────────────────
        # PROVEN MODEL: Matches backtesting code that produced validated ROI

        hca_spread_1h = 0.0 if is_neutral else self.hca_spread_1h
        hca_total_1h = 0.0 if is_neutral else self.hca_total_1h

        # First half spread: PROVEN formula from backtesting
        # Applies pace factor to full game spread (which includes HCA), then subtracts 1H HCA
        spread_1h = (spread + hca_for_spread) * self.config.first_half_pace_factor - hca_spread_1h

        # First half total: PROVEN formula from backtesting
        # Removes full game HCA, applies score factor, then adds minimal 1H HCA
        total_1h = (total - hca_for_total * 0.2) * self.config.first_half_score_factor + (hca_total_1h * 0.1)

        # Derive first half scores from full game scores (consistent with proven model)
        home_score_1h = home_score * self.config.first_half_score_factor
        away_score_1h = away_score * self.config.first_half_score_factor

        # ─────────────────────────────────────────────────────────────────────
        # WIN PROBABILITY & MONEYLINE
        # ─────────────────────────────────────────────────────────────────────

        home_win_prob = self._spread_to_win_prob(spread)
        home_win_prob_1h = self._spread_to_win_prob(spread_1h)

        home_ml = self._prob_to_american_odds(home_win_prob)
        away_ml = self._prob_to_american_odds(1 - home_win_prob)

        home_ml_1h = self._prob_to_american_odds(home_win_prob_1h)
        away_ml_1h = self._prob_to_american_odds(1 - home_win_prob_1h)

        return PredictorOutput(
            spread=round(spread, 1),
            total=round(total, 1),
            home_score=round(home_score, 1),
            away_score=round(away_score, 1),
            spread_1h=round(spread_1h, 1),
            total_1h=round(total_1h, 1),
            home_score_1h=round(home_score_1h, 1),
            away_score_1h=round(away_score_1h, 1),
            home_win_prob=round(home_win_prob, 3),
            home_win_prob_1h=round(home_win_prob_1h, 3),
            home_ml=home_ml,
            away_ml=away_ml,
            home_ml_1h=home_ml_1h,
            away_ml_1h=away_ml_1h,
        )

    def _spread_to_win_prob(self, spread: float) -> float:
        """
        Convert spread to win probability using normal CDF.

        Spread > 0 means home is favored (home wins by X points).
        Spread < 0 means away is favored.
        """
        # Using normal distribution approximation
        # sigma ~11 for college basketball spreads
        sigma = self.config.spread_to_ml_sigma

        # CDF of normal distribution
        # Positive spread = home favored = higher home win probability
        # BUT: Our spread convention is Negative = Home Favored.
        # So we invert the spread for this calculation.
        z = -spread / sigma
        prob = 0.5 * (1 + math.erf(z / math.sqrt(2)))

        return max(0.01, min(0.99, prob))

    def _prob_to_american_odds(self, prob: float) -> int:
        """Convert probability to American odds."""
        if prob >= 0.5:
            # Favorite: negative odds
            return int(-100 * prob / (1 - prob))
        else:
            # Underdog: positive odds
            return int(100 * (1 - prob) / prob)


class PredictionEngine:
    """
    Main prediction engine that orchestrates predictions and recommendations.
    """

    def __init__(self):
        self.predictor = BarttorkvikPredictor()
        self.config = settings.model

    def make_prediction(
        self,
        game_id: UUID,
        home_team: str,
        away_team: str,
        commence_time: datetime,
        home_ratings: TeamRatings,
        away_ratings: TeamRatings,
        market_odds: Optional[MarketOdds] = None,
        is_neutral: bool = False,
    ) -> Prediction:
        """
        Generate a full prediction for a game.

        Args:
            game_id: Unique game identifier
            home_team: Home team name
            away_team: Away team name
            commence_time: Game start time
            home_ratings: Barttorvik ratings for home team
            away_ratings: Barttorvik ratings for away team
            market_odds: Current market odds (optional)
            is_neutral: True if neutral site

        Returns:
            Complete Prediction object
        """
        # Generate raw predictions
        output = self.predictor.predict(home_ratings, away_ratings, is_neutral)

        # Calculate confidence based on sample quality
        spread_confidence = self._calculate_confidence(
            home_ratings, away_ratings, "spread"
        )
        total_confidence = self._calculate_confidence(
            home_ratings, away_ratings, "total"
        )

        # First half has slightly lower confidence (less data/signal)
        spread_confidence_1h = spread_confidence * 0.9
        total_confidence_1h = total_confidence * 0.9

        prediction = Prediction(
            game_id=game_id,
            home_team=home_team,
            away_team=away_team,
            commence_time=commence_time,
            predicted_spread=output.spread,
            predicted_total=output.total,
            predicted_home_score=output.home_score,
            predicted_away_score=output.away_score,
            spread_confidence=spread_confidence,
            total_confidence=total_confidence,
            predicted_spread_1h=output.spread_1h,
            predicted_total_1h=output.total_1h,
            predicted_home_score_1h=output.home_score_1h,
            predicted_away_score_1h=output.away_score_1h,
            spread_confidence_1h=spread_confidence_1h,
            total_confidence_1h=total_confidence_1h,
            predicted_home_ml=output.home_ml,
            predicted_away_ml=output.away_ml,
            predicted_home_ml_1h=output.home_ml_1h,
            predicted_away_ml_1h=output.away_ml_1h,
            home_win_prob=output.home_win_prob,
            home_win_prob_1h=output.home_win_prob_1h,
        )

        # Calculate edges if market odds available
        if market_odds:
            prediction.calculate_edges(market_odds)

        return prediction

    def _check_moneyline_value(
        self,
        prediction: Prediction,
        market_odds: MarketOdds,
    ) -> list[tuple]:
        """
        Check if moneylines offer value.

        Returns list of (bet_type, pick, ev_percent, confidence) tuples.
        """
        recommendations = []
        min_ev = 0.03  # Minimum 3% EV edge

        # Full game moneyline
        if market_odds.home_ml is not None and market_odds.away_ml is not None:
            # Convert market odds to implied probabilities
            home_market_prob = self._american_odds_to_prob(market_odds.home_ml)
            away_market_prob = self._american_odds_to_prob(market_odds.away_ml)

            # Calculate EV
            home_ev = prediction.home_win_prob - home_market_prob
            away_ev = (1 - prediction.home_win_prob) - away_market_prob

            if home_ev >= min_ev:
                recommendations.append((
                    BetType.MONEYLINE,
                    Pick.HOME,
                    home_ev * 100,
                    prediction.spread_confidence,
                    market_odds.home_ml,
                ))
            elif away_ev >= min_ev:
                recommendations.append((
                    BetType.MONEYLINE,
                    Pick.AWAY,
                    away_ev * 100,
                    prediction.spread_confidence,
                    market_odds.away_ml,
                ))

        # 1H moneyline
        if market_odds.home_ml_1h is not None and market_odds.away_ml_1h is not None:
            home_market_prob_1h = self._american_odds_to_prob(market_odds.home_ml_1h)
            away_market_prob_1h = self._american_odds_to_prob(market_odds.away_ml_1h)

            home_ev_1h = prediction.home_win_prob_1h - home_market_prob_1h
            away_ev_1h = (1 - prediction.home_win_prob_1h) - away_market_prob_1h

            if home_ev_1h >= min_ev:
                recommendations.append((
                    BetType.MONEYLINE_1H,
                    Pick.HOME,
                    home_ev_1h * 100,
                    prediction.spread_confidence_1h,
                    market_odds.home_ml_1h,
                ))
            elif away_ev_1h >= min_ev:
                recommendations.append((
                    BetType.MONEYLINE_1H,
                    Pick.AWAY,
                    away_ev_1h * 100,
                    prediction.spread_confidence_1h,
                    market_odds.away_ml_1h,
                ))

        return recommendations

    def _american_odds_to_prob(self, odds: int) -> float:
        """Convert American odds to implied probability (without vig)."""
        if odds < 0:
            return abs(odds) / (abs(odds) + 100)
        else:
            return 100 / (odds + 100)

    def generate_recommendations(
        self,
        prediction: Prediction,
        market_odds: MarketOdds,
    ) -> list[BettingRecommendation]:
        """
        Generate betting recommendations based on prediction edges.

        Only recommends bets that exceed minimum thresholds.
        """
        recommendations = []

        # Check each bet type
        bet_checks = [
            (
                BetType.SPREAD,
                prediction.predicted_spread,
                market_odds.spread,
                prediction.spread_edge,
                prediction.spread_confidence,
                self.config.min_spread_edge,
            ),
            (
                BetType.TOTAL,
                prediction.predicted_total,
                market_odds.total,
                prediction.total_edge,
                prediction.total_confidence,
                self.config.min_total_edge,
            ),
            (
                BetType.SPREAD_1H,
                prediction.predicted_spread_1h,
                market_odds.spread_1h,
                prediction.spread_edge_1h,
                prediction.spread_confidence_1h,
                self.config.min_spread_edge,
            ),
            (
                BetType.TOTAL_1H,
                prediction.predicted_total_1h,
                market_odds.total_1h,
                prediction.total_edge_1h,
                prediction.total_confidence_1h,
                self.config.min_total_edge,
            ),
        ]

        # Add moneyline checks if market odds available
        moneyline_checks = self._check_moneyline_value(prediction, market_odds)

        for bet_type, model_line, market_line, edge, confidence, min_edge in bet_checks:
            if market_line is None:
                continue

            if edge < min_edge:
                continue

            if confidence < self.config.min_confidence:
                continue

            # Determine pick direction
            if bet_type in (BetType.SPREAD, BetType.SPREAD_1H):
                # If model spread is more negative than market, take HOME
                # If model spread is more positive than market, take AWAY
                pick = Pick.HOME if model_line < market_line else Pick.AWAY
            else:
                # Totals: if model total > market, take OVER
                pick = Pick.OVER if model_line > market_line else Pick.UNDER


            # Calculate EV and Kelly
            ev_percent, kelly = self._calculate_ev_kelly(
                edge, confidence, bet_type
            )

            # Determine bet tier
            bet_tier = self._get_bet_tier(edge, confidence)

            # Get sharp line for comparison
            sharp_line = None
            is_sharp_aligned = True
            if bet_type == BetType.SPREAD:
                sharp_line = market_odds.sharp_spread
            elif bet_type == BetType.TOTAL:
                sharp_line = market_odds.sharp_total

            if sharp_line is not None:
                # Check if we're aligned with sharp movement
                is_sharp_aligned = self._check_sharp_alignment(
                    pick, model_line, market_line, sharp_line, bet_type
                )

            # Apply sharp alignment penalty if needed
            final_confidence = confidence
            if not is_sharp_aligned:
                final_confidence *= (1 - self.config.against_sharp_penalty)

            # Skip if confidence dropped below threshold
            if final_confidence < self.config.min_confidence:
                continue

            recommended_units = min(
                kelly * self.config.kelly_fraction * 10,  # Convert to units
                self.config.max_bet_units,
            )

            # FIX: Calculate actual market probability from odds instead of hardcoding 0.5
            # Standard -110 odds imply 52.38% probability (110/210)
            # This accounts for the vig/juice in the line
            if bet_type in (BetType.SPREAD, BetType.SPREAD_1H):
                # Use spread price if available, default to -110
                spread_price = getattr(market_odds, 'spread_price', -110) or -110
                market_prob = self._american_odds_to_prob(spread_price)
            elif bet_type in (BetType.TOTAL, BetType.TOTAL_1H):
                # Use over/under price, default to -110
                over_price = getattr(market_odds, 'over_price', -110) or -110
                market_prob = self._american_odds_to_prob(over_price)
            else:
                market_prob = 0.5  # Fallback for edge cases

            rec = BettingRecommendation(
                game_id=prediction.game_id,
                home_team=prediction.home_team,
                away_team=prediction.away_team,
                commence_time=prediction.commence_time,
                bet_type=bet_type,
                pick=pick,
                line=market_line,
                model_line=model_line,
                market_line=market_line,
                edge=edge,
                confidence=final_confidence,
                ev_percent=ev_percent,
                implied_prob=confidence,
                market_prob=market_prob,
                kelly_fraction=kelly,
                recommended_units=round(recommended_units, 1),
                bet_tier=bet_tier,
                sharp_line=sharp_line,
                is_sharp_aligned=is_sharp_aligned,
            )

            recommendations.append(rec)

        # Process moneyline recommendations
        for bet_type, pick, ev_percent, confidence, market_odds_value in moneyline_checks:
            if confidence < self.config.min_confidence:
                continue

            # Calculate Kelly fraction for moneyline
            # For moneyline, edge is the EV percentage
            kelly = ev_percent / 100.0  # Simple Kelly approximation

            # Determine bet tier based on EV
            if ev_percent >= 10.0:
                bet_tier = BetTier.MAX
            elif ev_percent >= 6.0:
                bet_tier = BetTier.MEDIUM
            else:
                bet_tier = BetTier.STANDARD

            recommended_units = min(
                kelly * self.config.kelly_fraction * 10,
                self.config.max_bet_units,
            )

            # Get model and market probabilities
            if bet_type == BetType.MONEYLINE:
                model_prob = prediction.home_win_prob if pick == Pick.HOME else (1 - prediction.home_win_prob)
            else:  # MONEYLINE_1H
                model_prob = prediction.home_win_prob_1h if pick == Pick.HOME else (1 - prediction.home_win_prob_1h)

            market_prob = self._american_odds_to_prob(market_odds_value)

            rec = BettingRecommendation(
                game_id=prediction.game_id,
                home_team=prediction.home_team,
                away_team=prediction.away_team,
                commence_time=prediction.commence_time,
                bet_type=bet_type,
                pick=pick,
                line=market_odds_value,  # For moneyline, "line" is the odds
                model_line=market_odds_value,  # Not really applicable for ML
                market_line=market_odds_value,
                edge=ev_percent,  # For ML, edge is EV %
                confidence=confidence,
                ev_percent=ev_percent,
                implied_prob=model_prob,
                market_prob=market_prob,
                kelly_fraction=kelly,
                recommended_units=round(recommended_units, 1),
                bet_tier=bet_tier,
                sharp_line=None,  # No sharp line tracking for ML yet
                is_sharp_aligned=True,
            )

            recommendations.append(rec)

        return recommendations

    def _calculate_confidence(
        self,
        home_ratings: TeamRatings,
        away_ratings: TeamRatings,
        bet_type: str,
    ) -> float:
        """
        Calculate prediction confidence based on data quality.

        Higher confidence when:
        - Both teams have more games played (more reliable ratings)
        - Net rating difference is larger (clearer skill gap)
        - Teams are higher ranked (more data/coverage)
        """
        # Base confidence
        confidence = 0.70

        # Games played factor (more games = more reliable ratings)
        # This would need actual games_played data from ratings
        # For now, use rank as proxy (higher ranked = more coverage)
        rank_factor = 1.0 - (min(home_ratings.rank, away_ratings.rank) / 400)
        confidence += rank_factor * 0.1

        # Net rating difference factor (larger gap = more confident)
        net_diff = abs(home_ratings.net_rating - away_ratings.net_rating)
        if net_diff > 15:
            confidence += 0.1
        elif net_diff > 10:
            confidence += 0.05

        return min(0.95, confidence)

    def _calculate_ev_kelly(
        self,
        edge: float,
        confidence: float,
        bet_type: BetType,
    ) -> tuple[float, float]:
        """
        Calculate expected value percentage and Kelly criterion.

        Assumes standard -110 odds (bet $110 to win $100).
        """
        # Standard -110 juice implies ~52.38% needed to break even
        break_even = 0.5238

        # Our implied probability based on edge
        # Edge in points roughly translates to probability advantage
        edge_prob = edge / 30  # ~30 points = 100% probability shift

        our_prob = break_even + edge_prob * confidence

        # EV = (prob * win) - ((1-prob) * loss)
        # At -110: win = 100, loss = 110
        ev = (our_prob * 100) - ((1 - our_prob) * 110)
        ev_percent = ev / 110 * 100  # As percentage of stake

        # Kelly: f* = (bp - q) / b
        # b = odds ratio (100/110 for -110)
        # p = probability of winning
        # q = 1 - p
        b = 100 / 110
        p = our_prob
        q = 1 - p

        kelly = max(0, (b * p - q) / b)

        return round(ev_percent, 2), round(kelly, 4)

    def _get_bet_tier(self, edge: float, confidence: float) -> BetTier:
        """Determine bet tier based on edge and confidence."""
        score = edge * confidence

        if score >= 3.0:
            return BetTier.MAX
        elif score >= 2.0:
            return BetTier.MEDIUM
        else:
            return BetTier.STANDARD

    def _check_sharp_alignment(
        self,
        pick: Pick,
        model_line: float,
        market_line: float,
        sharp_line: float,
        bet_type: BetType,
    ) -> bool:
        """
        Check if our pick aligns with sharp book movement.

        Sharp books (Pinnacle, Circa) are considered the "truth".
        If the sharp line has moved in the same direction as our edge,
        we're more confident. If it moved against us, we're less confident.
        """
        if bet_type in (BetType.SPREAD, BetType.SPREAD_1H):
            # For spreads:
            # If we like HOME (model < market), and sharp moved DOWN, aligned
            # If we like AWAY (model > market), and sharp moved UP, aligned
            sharp_moved_down = sharp_line < market_line
            sharp_moved_up = sharp_line > market_line

            if pick == Pick.HOME:
                return sharp_moved_down or sharp_line <= model_line
            else:
                return sharp_moved_up or sharp_line >= model_line
        else:
            # For totals:
            # If we like OVER (model > market), and sharp moved UP, aligned
            # If we like UNDER (model < market), and sharp moved DOWN, aligned
            sharp_moved_up = sharp_line > market_line
            sharp_moved_down = sharp_line < market_line

            if pick == Pick.OVER:
                return sharp_moved_up or sharp_line >= model_line
            else:
                return sharp_moved_down or sharp_line <= model_line


# Singleton instance
prediction_engine = PredictionEngine()
