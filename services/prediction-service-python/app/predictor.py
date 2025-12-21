"""
Green Bier Sports - NCAAM Prediction Engine v6.3

SINGLE SOURCE OF TRUTH: All predictions flow through this service.

v6.3 CHANGES (2024-12-20):
- ALL 22 BARTTORVIK FIELDS NOW REQUIRED - no fallbacks, no defaults
- TeamRatings dataclass now enforces all fields present
- Data pipeline guarantees complete data or explicit failure

v6.2 CHANGES (2024-12-20):
- NEW: Situational adjustments (rest days, back-to-back detection)
- NEW: Dynamic variance modeling (3PR + tempo differential)
- NEW: Enhanced 1H predictions (EFG-based dynamic factors)

v6.1 CHANGES (2024-12-20):
- FIXED: Total formula was inflating by 15-20 pts (multiplicative error)
- Spread: Uses net rating difference (Home_Net - Away_Net)/2 + HCA
- Total: Uses simple efficiency (AdjO * Tempo / 100) for each team
- HCA values now EXPLICIT in config (no hidden multipliers)

HCA Values (from config.py - applied directly):
- Full Game Spreads: 3.0 points
- Full Game Totals: 0.9 points
- First Half Spreads: 1.5 points
- First Half Totals: 0.225 points

Core Formulas:
- Spread = -((Home_Net - Away_Net)/2 + HCA + Situational_Adj)
- Total = (Home_AdjO + Away_AdjO) * AvgTempo / 100 + HCA_total + Situational_Adj
- 1H Spread = -(raw_margin * margin_scale + HCA_1h)  [dynamic margin_scale]
- 1H Total = tempo_factor calculation + HCA_total_1h  [dynamic tempo_factor]
- Moneylines: Normal CDF conversion (dynamic sigma based on 3PR/tempo)

All 6 markets: FG Spread/Total/ML, 1H Spread/Total/ML
"""

import math
from dataclasses import dataclass, field
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
from app.situational import SituationalAdjuster, SituationalAdjustment, RestInfo
from app.variance import DynamicVarianceCalculator, VarianceFactors
from app.first_half import EnhancedFirstHalfCalculator, FirstHalfFactors
import structlog


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

    # Enhancement tracking (v6.2)
    variance: float = 11.0  # Dynamic sigma used
    variance_1h: float = 12.65  # 1H variance
    situational_adj: Optional[SituationalAdjustment] = None
    first_half_factors: Optional[FirstHalfFactors] = None
    matchup_adj: float = 0.0  # v6.3 Matchup adjustment (ORB/TOR)


class BarttorkvikPredictor:
    """
    Simplified Barttorvik efficiency-based predictor with v6.3 enhancements.

    v6.3: ALL 22 BARTTORVIK FIELDS REQUIRED - no fallbacks, no defaults.
    TeamRatings dataclass now enforces all fields present.

    Core Formula:
        Spread = Home_NetRtg - Away_NetRtg + HCA + Situational_Adj

    Where:
        NetRtg = AdjO - AdjD

    This is the fundamental efficiency model with situational adjustments,
    dynamic variance, and enhanced 1H predictions.
    """

    def __init__(self):
        self.config = settings.model
        # MODULAR HCA - loaded from config.py (single source of truth)
        self.hca_spread = self.config.home_court_advantage_spread
        self.hca_total = self.config.home_court_advantage_total
        self.hca_spread_1h = self.config.home_court_advantage_spread_1h
        self.hca_total_1h = self.config.home_court_advantage_total_1h

        # v6.2 Enhancement calculators
        self.situational = SituationalAdjuster(
            b2b_penalty=self.config.b2b_penalty,
            one_day_penalty=self.config.one_day_rest_penalty,
            rest_diff_factor=self.config.rest_differential_factor,
            max_rest_diff_adj=self.config.max_rest_differential_adj,
            enabled=self.config.situational_enabled,
        )

        self.variance_calc = DynamicVarianceCalculator(
            base_sigma=self.config.base_sigma,
            three_pt_variance_factor=self.config.three_pt_variance_factor,
            pace_variance_factor=self.config.pace_variance_factor,
            min_sigma=self.config.min_sigma,
            max_sigma=self.config.max_sigma,
            enabled=self.config.dynamic_variance_enabled,
        )

        self.first_half_calc = EnhancedFirstHalfCalculator(
            base_tempo_factor=self.config.first_half_base_tempo_factor,
            base_margin_scale=self.config.first_half_base_margin_scale,
            efg_tempo_adjustment=self.config.efg_tempo_adjustment,
            efg_margin_adjustment=self.config.efg_margin_adjustment,
            enabled=self.config.enhanced_1h_enabled,
        )
        
        # Initialize logger
        self.logger = structlog.get_logger()

    def predict(
        self,
        home_ratings: TeamRatings,
        away_ratings: TeamRatings,
        is_neutral: bool = False,
        home_rest: Optional[RestInfo] = None,
        away_rest: Optional[RestInfo] = None,
    ) -> PredictorOutput:
        """
        Generate predictions for a matchup.

        v6.3: TeamRatings MUST contain all 22 Barttorvik fields.
        No fallbacks, no defaults - data pipeline ensures complete data.

        Args:
            home_ratings: Barttorvik ratings for home team (ALL 22 FIELDS REQUIRED)
            away_ratings: Barttorvik ratings for away team (ALL 22 FIELDS REQUIRED)
            is_neutral: True if neutral site game
            home_rest: Rest info for home team (for situational adjustments)
            away_rest: Rest info for away team (for situational adjustments)

        Returns:
            PredictorOutput with all predictions
        """
        self.logger.info(f"Starting prediction for {home_ratings.team} vs {away_ratings.team}")

        # ─────────────────────────────────────────────────────────────────────
        # v6.2 ENHANCEMENTS - Situational, Variance, 1H Factors
        # ─────────────────────────────────────────────────────────────────────

        # 1. Calculate situational adjustment (rest days, B2B)
        sit_adj = None
        situational_spread_adj = 0.0
        situational_total_adj = 0.0
        if home_rest and away_rest:
            sit_adj = self.situational.compute_adjustment(home_rest, away_rest)
            situational_spread_adj = sit_adj.spread_adjustment
            situational_total_adj = sit_adj.total_adjustment

        # 2. Calculate dynamic variance
        variance_factors = self.variance_calc.calculate_game_variance(
            home_three_pt_rate=home_ratings.three_pt_rate,
            away_three_pt_rate=away_ratings.three_pt_rate,
            home_tempo=home_ratings.tempo,
            away_tempo=away_ratings.tempo,
        )
        game_sigma = variance_factors.sigma
        h1_sigma = self.variance_calc.calculate_1h_variance(
            variance_factors, self.config.variance_1h_multiplier
        )

        # 3. Calculate dynamic 1H factors
        h1_factors = self.first_half_calc.calculate_factors(
            home_efg=home_ratings.efg,
            away_efg=away_ratings.efg,
            home_tempo=home_ratings.tempo,
            away_tempo=away_ratings.tempo,
        )

        # 4. Calculate Matchup Adjustments (Rebounding, Turnovers)
        matchup_adj = self._calculate_matchup_adjustments(home_ratings, away_ratings)

        # ─────────────────────────────────────────────────────────────────────
        # SCORE PREDICTIONS - CORRECTED FORMULA (v6.3)
        # ─────────────────────────────────────────────────────────────────────
        # 1. Expected Tempo (Home + Away - Avg)
        avg_tempo = home_ratings.tempo + away_ratings.tempo - self.config.league_avg_tempo

        # 2. Expected Efficiency (Off + Def - Avg)
        home_eff = home_ratings.adj_o + away_ratings.adj_d - self.config.league_avg_efficiency
        away_eff = away_ratings.adj_o + home_ratings.adj_d - self.config.league_avg_efficiency

        # 3. Base Scores (Efficiency * Tempo / 100)
        home_score_base = home_eff * avg_tempo / 100.0
        away_score_base = away_eff * avg_tempo / 100.0

        # 4. Apply HCA & Situational & Matchup
        hca_for_spread = 0.0 if is_neutral else self.hca_spread
        hca_for_total = 0.0 if is_neutral else self.hca_total

        # Total = Sum of scores + HCA + Situational
        # Note: Matchup adjustments (ORB/TOR) primarily affect efficiency/margin, not necessarily total pace/score directly in this model
        total = home_score_base + away_score_base + hca_for_total + situational_total_adj

        # Spread = -(Home - Away + HCA + Situational + Matchup)
        # Note: Spread is negative when Home is favored
        # Matchup Adj: Positive value means Home Advantage -> More negative spread
        raw_margin = home_score_base - away_score_base
        spread = -(raw_margin + hca_for_spread + situational_spread_adj + matchup_adj)
        
        # Derive final scores from spread and total for consistency
        # (This ensures spread/total match the individual team scores exactly)
        home_score = (total - spread) / 2
        away_score = (total + spread) / 2

        # ─────────────────────────────────────────────────────────────────────
        # FIRST HALF PREDICTIONS - ENHANCED (v6.2)
        # ─────────────────────────────────────────────────────────────────────
        # Use dynamic factors based on EFG differential

        hca_spread_1h = 0.0 if is_neutral else self.hca_spread_1h
        hca_total_1h = 0.0 if is_neutral else self.hca_total_1h

        # 1H Spread: Use dynamic margin scale on the NEW raw margin
        spread_1h = -(raw_margin * h1_factors.margin_scale + hca_spread_1h)

        # 1H Total: Use dynamic tempo factor on the NEW avg tempo
        # Note: We use the base efficiency scores scaled by tempo factor
        home_score_1h = home_score_base * h1_factors.tempo_factor
        away_score_1h = away_score_base * h1_factors.tempo_factor
        total_1h = home_score_1h + away_score_1h + hca_total_1h

        # ─────────────────────────────────────────────────────────────────────
        # WIN PROBABILITY & MONEYLINE - DYNAMIC VARIANCE (v6.2)
        # ─────────────────────────────────────────────────────────────────────

        home_win_prob = self._spread_to_win_prob(spread, sigma=game_sigma)
        home_win_prob_1h = self._spread_to_win_prob(spread_1h, sigma=h1_sigma)

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
            # v6.2 enhancement tracking
            variance=game_sigma,
            variance_1h=h1_sigma,
            situational_adj=sit_adj,
            first_half_factors=h1_factors,
            matchup_adj=matchup_adj,
        )

    def _calculate_matchup_adjustments(self, home: TeamRatings, away: TeamRatings) -> float:
        """
        Calculate specific matchup advantages based on Four Factors.
        Returns points to ADD to Home Margin (Positive = Home Advantage).
        
        Based on docs/BARTTORVIK_FIELDS.md:
        - Rebounding Edge: ~0.15 pts per % edge
        - Turnover Edge: ~0.10 pts per % edge
        - Free Throw Edge: ~0.15 pts per % edge (Estimated)
        """
        adjustment = 0.0
        avg_orb = self.config.league_avg_orb
        avg_tor = self.config.league_avg_tor
        avg_ftr = self.config.league_avg_ftr

        # 1. Rebounding Edge (ORB% vs Opponent Allowed ORB%)
        # Home ORB Advantage = (Home ORB - Avg) + (Away Allowed ORB - Avg)
        # Away Allowed ORB = 100 - Away DRB
        home_orb_adv = (home.orb - avg_orb) + ((100 - away.drb) - avg_orb)
        away_orb_adv = (away.orb - avg_orb) + ((100 - home.drb) - avg_orb)
        
        net_orb_edge = home_orb_adv - away_orb_adv
        adjustment += net_orb_edge * 0.15

        # 2. Turnover Edge (TO% vs Opponent Forced TO%)
        # Home TO Disadvantage = (Home TOR - Avg) - (Away TORD - Avg)
        # Note: Higher TOR is BAD. Higher TORD is GOOD.
        # If Home TOR is 25 (+5 bad) and Away TORD is 25 (+5 good), Home is in trouble.
        # Expected Home TO% = Avg + (Home - Avg) + (Away_Forced - Avg)
        exp_home_tor = avg_tor + (home.tor - avg_tor) + (away.tord - avg_tor)
        exp_away_tor = avg_tor + (away.tor - avg_tor) + (home.tord - avg_tor)
        
        # Net TO% Edge (Negative diff means Home commits fewer TOs -> Good)
        # If Home commits 15% and Away commits 25%, Home has +10% edge.
        net_tor_edge = exp_away_tor - exp_home_tor
        adjustment += net_tor_edge * 0.10

        # 3. Free Throw Edge (FTR vs Opponent Allowed FTR)
        # FTR = FTA / FGA. Higher is better for offense.
        # Expected Home FTR = Avg + (Home FTR - Avg) + (Away FTRD - Avg)
        exp_home_ftr = avg_ftr + (home.ftr - avg_ftr) + (away.ftrd - avg_ftr)
        exp_away_ftr = avg_ftr + (away.ftr - avg_ftr) + (home.ftrd - avg_ftr)

        net_ftr_edge = exp_home_ftr - exp_away_ftr
        adjustment += net_ftr_edge * 0.15

        return adjustment

    def _spread_to_win_prob(self, spread: float, sigma: Optional[float] = None) -> float:
        """
        Convert spread to win probability using normal CDF.

        Spread > 0 means home is favored (home wins by X points).
        Spread < 0 means away is favored.

        Args:
            spread: Predicted spread
            sigma: Standard deviation for conversion (default from config)
        """
        # Use dynamic sigma if provided, otherwise use config default
        if sigma is None:
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
        home_rest: Optional[RestInfo] = None,
        away_rest: Optional[RestInfo] = None,
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
            home_rest: Rest info for home team (optional, for situational adjustments)
            away_rest: Rest info for away team (optional, for situational adjustments)

        Returns:
            Complete Prediction object
        """
        # Generate raw predictions with v6.2 enhancements
        output = self.predictor.predict(
            home_ratings, away_ratings, is_neutral, home_rest, away_rest
        )

        # Calculate confidence based on sample quality
        spread_confidence = self._calculate_confidence(
            home_ratings, away_ratings, "spread"
        )
        total_confidence = self._calculate_confidence(
            home_ratings, away_ratings, "total"
        )

        # First half confidence: use dynamic scale from 1H factors if available
        h1_conf_scale = 0.9
        if output.first_half_factors:
            h1_conf_scale = output.first_half_factors.confidence_scale
        spread_confidence_1h = spread_confidence * h1_conf_scale
        total_confidence_1h = total_confidence * h1_conf_scale

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
            model_version="v6.3",
        )

        # Calculate edges if market odds available
        if market_odds:
            prediction.calculate_edges(market_odds)

        return prediction

    def _ev_and_kelly_from_prob(self, model_prob: float, odds: int) -> tuple[float, float, float]:
        """Return (ev_percent, kelly_fraction, market_implied_prob) for a moneyline."""
        market_prob = self._american_odds_to_prob(odds)

        # Profit multiple for 1 unit stake
        if odds >= 0:
            b = odds / 100.0
        else:
            b = 100.0 / abs(odds)

        ev_percent = (model_prob * b - (1 - model_prob)) * 100.0
        kelly = max(0.0, (b * model_prob - (1 - model_prob)) / b)

        return round(ev_percent, 2), round(kelly, 4), market_prob

    def _check_moneyline_value(
        self,
        prediction: Prediction,
        market_odds: MarketOdds,
    ) -> list[tuple]:
        """
        Check if moneylines offer value.

        Returns list of (bet_type, pick, ev_percent, model_prob, market_prob, kelly, odds, confidence).
        """
        recommendations = []
        min_ev_pct = 3.0  # Require at least +3% EV relative to stake

        # Full game moneyline
        if market_odds.home_ml is not None and market_odds.away_ml is not None:
            home_ev, home_kelly, home_market_prob = self._ev_and_kelly_from_prob(
                prediction.home_win_prob,
                market_odds.home_ml,
            )
            away_ev, away_kelly, away_market_prob = self._ev_and_kelly_from_prob(
                1 - prediction.home_win_prob,
                market_odds.away_ml,
            )

            if home_ev >= min_ev_pct:
                recommendations.append((
                    BetType.MONEYLINE,
                    Pick.HOME,
                    home_ev,
                    prediction.spread_confidence,
                    prediction.home_win_prob,
                    home_market_prob,
                    home_kelly,
                    market_odds.home_ml,
                ))
            if away_ev >= min_ev_pct:
                recommendations.append((
                    BetType.MONEYLINE,
                    Pick.AWAY,
                    away_ev,
                    prediction.spread_confidence,
                    1 - prediction.home_win_prob,
                    away_market_prob,
                    away_kelly,
                    market_odds.away_ml,
                ))

        # 1H moneyline
        if market_odds.home_ml_1h is not None and market_odds.away_ml_1h is not None:
            home_ev_1h, home_kelly_1h, home_market_prob_1h = self._ev_and_kelly_from_prob(
                prediction.home_win_prob_1h,
                market_odds.home_ml_1h,
            )
            away_ev_1h, away_kelly_1h, away_market_prob_1h = self._ev_and_kelly_from_prob(
                1 - prediction.home_win_prob_1h,
                market_odds.away_ml_1h,
            )

            if home_ev_1h >= min_ev_pct:
                recommendations.append((
                    BetType.MONEYLINE_1H,
                    Pick.HOME,
                    home_ev_1h,
                    prediction.spread_confidence_1h,
                    prediction.home_win_prob_1h,
                    home_market_prob_1h,
                    home_kelly_1h,
                    market_odds.home_ml_1h,
                ))
            if away_ev_1h >= min_ev_pct:
                recommendations.append((
                    BetType.MONEYLINE_1H,
                    Pick.AWAY,
                    away_ev_1h,
                    prediction.spread_confidence_1h,
                    1 - prediction.home_win_prob_1h,
                    away_market_prob_1h,
                    away_kelly_1h,
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
            if bet_type == BetType.SPREAD:
                spread_price = getattr(market_odds, 'spread_price', None) or -110
                market_prob = self._american_odds_to_prob(spread_price)
            elif bet_type == BetType.SPREAD_1H:
                spread_price = getattr(market_odds, 'spread_price_1h', None) or -110
                market_prob = self._american_odds_to_prob(spread_price)
            elif bet_type == BetType.TOTAL:
                over_price = getattr(market_odds, 'over_price', None) or -110
                market_prob = self._american_odds_to_prob(over_price)
            elif bet_type == BetType.TOTAL_1H:
                over_price = getattr(market_odds, 'over_price_1h', None) or -110
                market_prob = self._american_odds_to_prob(over_price)
            else:
                market_prob = 0.5

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
        for (
            bet_type,
            pick,
            ev_percent,
            confidence,
            model_prob,
            market_prob,
            kelly,
            market_odds_value,
        ) in moneyline_checks:
            if confidence < self.config.min_confidence:
                continue

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
