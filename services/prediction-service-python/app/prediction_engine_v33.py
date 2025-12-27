"""
NCAA Prediction Engine v33.6

Orchestrator for modular market-specific prediction models.
Provides drop-in replacement for BarttorvikPredictor (v6.3.25).

Each market has its own independently-backtested model:
- FG Spread: v33.6 (3,318 games, MAE 10.57, HCA 5.8)
- FG Total: v33.6 (3,318 games, MAE 13.1, Calibration +7.0)
- 1H Spread: v33.6 (904 games, MAE 8.25, HCA 3.6)
- 1H Total: v33.6 (562 games, MAE 8.88, Calibration +2.7)
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from app.models import (
    BetTier,
    BetType,
    BettingRecommendation,
    MarketOdds,
    Pick,
    Prediction,
    TeamRatings,
)
from app.predictors import (
    fg_spread_model,
    fg_total_model,
    h1_spread_model,
    h1_total_model,
)
from app.config import settings
import structlog


# Extreme total thresholds - predictions outside these ranges are unreliable
# From backtest: FG model under-predicts high games, over-predicts low games
FG_TOTAL_MIN_RELIABLE = 120.0  # Below this, model over-predicts
FG_TOTAL_MAX_RELIABLE = 170.0  # Above this, model under-predicts
H1_TOTAL_MIN_RELIABLE = 55.0   # Below this, model over-predicts
H1_TOTAL_MAX_RELIABLE = 85.0   # Above this, model under-predicts


class PredictionEngineV33:
    """
    v33.6 Prediction Engine - Modular architecture with 4 independent models.
    
    Provides same interface as BarttorvikPredictor for drop-in replacement.
    """

    def __init__(self):
        """Initialize with v33.6 modular models."""
        self.config = settings.model
        self.logger = structlog.get_logger()
        
        # Store models for reference
        self.fg_spread_model = fg_spread_model
        self.fg_total_model = fg_total_model
        self.h1_spread_model = h1_spread_model
        self.h1_total_model = h1_total_model

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
        home_rest: Optional['RestInfo'] = None,
        away_rest: Optional['RestInfo'] = None,
    ) -> Prediction:
        """
        Generate predictions using v33.6 modular models.
        
        Each market gets its own specialized model:
        - FG Spread: Proven statistical edge
        - FG Total: Hybrid approach
        - 1H Spread: Independent calibration
        - 1H Total: Independent calibration
        
        Args:
            game_id: Unique game identifier
            home_team: Home team name
            away_team: Away team name
            commence_time: Game start time
            home_ratings: Barttorvik ratings (all 22 fields required)
            away_ratings: Barttorvik ratings (all 22 fields required)
            market_odds: Current market odds (optional)
            is_neutral: True if neutral site game
            home_rest: Rest info for situational adjustments (optional)
            away_rest: Rest info for situational adjustments (optional)
            
        Returns:
            Complete Prediction object with all 4 market predictions
        """
        if home_ratings is None or away_ratings is None:
            raise ValueError("home_ratings and away_ratings are required")

        self.logger.info(
            f"v33.6: Predicting {home_team} vs {away_team}",
            game_id=str(game_id),
            models=["FGSpread", "FGTotal", "H1Spread", "H1Total"]
        )

        # ═══════════════════════════════════════════════════════════════════════
        # Get predictions from each independent model
        # ═══════════════════════════════════════════════════════════════════════

        # FG Spread (independent, backtested on 3,318 games)
        fg_spread_pred = self.fg_spread_model.predict(
            home=home_ratings,
            away=away_ratings,
            is_neutral=is_neutral,
            home_rest_days=home_rest.days_since_game if home_rest else None,
            away_rest_days=away_rest.days_since_game if away_rest else None,
        )

        # FG Total (independent, backtested on 3,318 games)
        fg_total_pred = self.fg_total_model.predict(
            home=home_ratings,
            away=away_ratings,
            is_neutral=is_neutral,
            home_rest_days=home_rest.days_since_game if home_rest else None,
            away_rest_days=away_rest.days_since_game if away_rest else None,
        )

        # 1H Spread (independent, backtested on 904 games)
        h1_spread_pred = self.h1_spread_model.predict(
            home=home_ratings,
            away=away_ratings,
            is_neutral=is_neutral,
            home_rest_days=home_rest.days_since_game if home_rest else None,
            away_rest_days=away_rest.days_since_game if away_rest else None,
        )

        # 1H Total (independent, backtested on 562 games)
        h1_total_pred = self.h1_total_model.predict(
            home=home_ratings,
            away=away_ratings,
            is_neutral=is_neutral,
            home_rest_days=home_rest.days_since_game if home_rest else None,
            away_rest_days=away_rest.days_since_game if away_rest else None,
        )

        # ═══════════════════════════════════════════════════════════════════════
        # Convert model predictions to Prediction object
        # ═══════════════════════════════════════════════════════════════════════

        # Derive implied scores from spread and total (for consistency)
        fg_spread = fg_spread_pred.value
        fg_total = fg_total_pred.value
        fg_home_score = (fg_total - fg_spread) / 2
        fg_away_score = (fg_total + fg_spread) / 2

        h1_spread = h1_spread_pred.value
        h1_total = h1_total_pred.value
        h1_home_score = (h1_total - h1_spread) / 2
        h1_away_score = (h1_total + h1_spread) / 2

        # Create Prediction object
        prediction = Prediction(
            game_id=game_id,
            home_team=home_team,
            away_team=away_team,
            commence_time=commence_time,
            # FG Predictions
            predicted_spread=fg_spread,
            predicted_total=fg_total,
            predicted_home_score=fg_home_score,
            predicted_away_score=fg_away_score,
            spread_confidence=fg_spread_pred.confidence,
            total_confidence=fg_total_pred.confidence,
            # 1H Predictions
            predicted_spread_1h=h1_spread,
            predicted_total_1h=h1_total,
            predicted_home_score_1h=h1_home_score,
            predicted_away_score_1h=h1_away_score,
            spread_confidence_1h=h1_spread_pred.confidence,
            total_confidence_1h=h1_total_pred.confidence,
            # Model metadata
            model_version="v33.6.1",
        )

        # Calculate edges if market odds available
        if market_odds:
            prediction.calculate_edges(market_odds)

        return prediction

    def generate_recommendations(
        self,
        prediction: Prediction,
        market_odds: MarketOdds,
    ) -> List[BettingRecommendation]:
        """
        Generate betting recommendations from predictions and market odds.
        
        Uses model-specific minimum edges and confidence thresholds.
        
        Args:
            prediction: Prediction object from make_prediction()
            market_odds: Current market odds
            
        Returns:
            List of BettingRecommendation objects
        """
        recommendations = []

        # ─────────────────────────────────────────────────────────────────────
        # FG SPREAD RECOMMENDATIONS
        # ─────────────────────────────────────────────────────────────────────
        if market_odds.spread is not None and prediction.spread_edge >= self.fg_spread_model.MIN_EDGE:
            if prediction.spread_confidence >= self.config.min_confidence:
                pick = Pick.HOME if prediction.predicted_spread < market_odds.spread else Pick.AWAY
                rec = self._create_recommendation(
                    prediction,
                    BetType.SPREAD,
                    pick,
                    prediction.predicted_spread,
                    market_odds.spread,
                    prediction.spread_edge,
                    prediction.spread_confidence,
                    market_odds,
                )
                if rec:
                    recommendations.append(rec)

        # ─────────────────────────────────────────────────────────────────────
        # FG TOTAL RECOMMENDATIONS
        # ─────────────────────────────────────────────────────────────────────
        # Skip extreme totals - model is unreliable at extremes (regression to mean)
        fg_total_in_range = FG_TOTAL_MIN_RELIABLE <= prediction.predicted_total <= FG_TOTAL_MAX_RELIABLE
        if not fg_total_in_range:
            self.logger.info(
                f"Skipping FG total bet - prediction {prediction.predicted_total:.1f} outside reliable range "
                f"({FG_TOTAL_MIN_RELIABLE}-{FG_TOTAL_MAX_RELIABLE})"
            )
        if market_odds.total is not None and prediction.total_edge >= self.fg_total_model.MIN_EDGE and fg_total_in_range:
            if prediction.total_confidence >= self.config.min_confidence:
                pick = Pick.OVER if prediction.predicted_total > market_odds.total else Pick.UNDER
                rec = self._create_recommendation(
                    prediction,
                    BetType.TOTAL,
                    pick,
                    prediction.predicted_total,
                    market_odds.total,
                    prediction.total_edge,
                    prediction.total_confidence,
                    market_odds,
                )
                if rec:
                    recommendations.append(rec)

        # ─────────────────────────────────────────────────────────────────────
        # 1H SPREAD RECOMMENDATIONS
        # ─────────────────────────────────────────────────────────────────────
        if market_odds.spread_1h is not None and prediction.spread_edge_1h >= self.h1_spread_model.MIN_EDGE:
            if prediction.spread_confidence_1h >= self.config.min_confidence:
                pick = Pick.HOME if prediction.predicted_spread_1h < market_odds.spread_1h else Pick.AWAY
                rec = self._create_recommendation(
                    prediction,
                    BetType.SPREAD_1H,
                    pick,
                    prediction.predicted_spread_1h,
                    market_odds.spread_1h,
                    prediction.spread_edge_1h,
                    prediction.spread_confidence_1h,
                    market_odds,
                )
                if rec:
                    recommendations.append(rec)

        # ─────────────────────────────────────────────────────────────────────
        # 1H TOTAL RECOMMENDATIONS
        # ─────────────────────────────────────────────────────────────────────
        # Skip extreme 1H totals - model is unreliable at extremes
        h1_total_in_range = H1_TOTAL_MIN_RELIABLE <= prediction.predicted_total_1h <= H1_TOTAL_MAX_RELIABLE
        if not h1_total_in_range:
            self.logger.info(
                f"Skipping 1H total bet - prediction {prediction.predicted_total_1h:.1f} outside reliable range "
                f"({H1_TOTAL_MIN_RELIABLE}-{H1_TOTAL_MAX_RELIABLE})"
            )
        if market_odds.total_1h is not None and prediction.total_edge_1h >= self.h1_total_model.MIN_EDGE and h1_total_in_range:
            if prediction.total_confidence_1h >= self.config.min_confidence:
                pick = Pick.OVER if prediction.predicted_total_1h > market_odds.total_1h else Pick.UNDER
                rec = self._create_recommendation(
                    prediction,
                    BetType.TOTAL_1H,
                    pick,
                    prediction.predicted_total_1h,
                    market_odds.total_1h,
                    prediction.total_edge_1h,
                    prediction.total_confidence_1h,
                    market_odds,
                )
                if rec:
                    recommendations.append(rec)

        return recommendations

    def _create_recommendation(
        self,
        prediction: Prediction,
        bet_type: BetType,
        pick: Pick,
        model_line: float,
        market_line: float,
        edge: float,
        confidence: float,
        market_odds: MarketOdds,
    ) -> Optional[BettingRecommendation]:
        """
        Create a single BettingRecommendation.
        
        Handles conversion to Pick perspective (for AWAY picks, flip spread sign).
        """
        # Store bet line from PICK perspective
        bet_line = market_line
        if bet_type in (BetType.SPREAD, BetType.SPREAD_1H):
            bet_line = market_line if pick == Pick.HOME else -market_line

        # Calculate EV and Kelly
        ev_percent, kelly = self._calculate_ev_kelly(edge, confidence, bet_type)

        # Determine bet tier
        bet_tier = self._get_bet_tier(edge, confidence)

        # Get sharp line for comparison
        sharp_line = None
        is_sharp_aligned = True
        if bet_type in (BetType.SPREAD, BetType.SPREAD_1H):
            sharp_line = market_odds.sharp_spread
        else:
            sharp_line = market_odds.sharp_total

        # Check sharp alignment
        if sharp_line is not None:
            is_sharp_aligned = self._check_sharp_alignment(
                pick, model_line, market_line, sharp_line, bet_type
            )

        # Apply sharp alignment penalty
        final_confidence = confidence
        if not is_sharp_aligned:
            final_confidence *= (1 - self.config.against_sharp_penalty)

        # Skip if confidence dropped below threshold
        if final_confidence < self.config.min_confidence:
            return None

        # Calculate recommended units
        recommended_units = min(
            kelly * self.config.kelly_fraction * 10,
            self.config.max_bet_units,
        )

        # Get market probability from odds
        market_prob = self._get_market_probability(bet_type, market_odds, pick)

        return BettingRecommendation(
            game_id=prediction.game_id,
            home_team=prediction.home_team,
            away_team=prediction.away_team,
            commence_time=prediction.commence_time,
            bet_type=bet_type,
            pick=pick,
            line=bet_line,
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

    def _calculate_ev_kelly(
        self,
        edge: float,
        confidence: float,
        bet_type: BetType,
    ) -> tuple[float, float]:
        """Calculate expected value percentage and Kelly criterion."""
        break_even = 0.5238  # -110 odds threshold

        # Edge probability impact
        edge_prob = edge / 30.0
        our_prob = break_even + edge_prob * confidence

        # EV = (prob * win) - ((1-prob) * loss)
        # At -110: win = 100, loss = 110
        ev = (our_prob * 100) - ((1 - our_prob) * 110)
        ev_percent = ev / 110 * 100

        # Kelly: f* = (bp - q) / b
        b = 100 / 110
        p = our_prob
        q = 1 - p
        kelly = max(0, (b * p - q) / b) if b > 0 else 0

        return ev_percent, kelly

    def _get_bet_tier(self, edge: float, confidence: float) -> BetTier:
        """Determine bet tier based on edge and confidence."""
        if edge >= 5.0 and confidence >= 0.75:
            return BetTier.MAX
        elif edge >= 3.0 and confidence >= 0.70:
            return BetTier.MEDIUM
        else:
            return BetTier.STANDARD

    def _check_sharp_alignment(
        self,
        pick: Pick,
        model_line: float,
        market_line: float,
        sharp_line: Optional[float],
        bet_type: BetType,
    ) -> bool:
        """Check if we're aligned with sharp movement."""
        if sharp_line is None:
            return True

        if bet_type in (BetType.SPREAD, BetType.SPREAD_1H):
            # For spreads: model and sharp should agree on direction
            model_favors_home = model_line < market_line
            sharp_favors_home = sharp_line < market_line
            return model_favors_home == sharp_favors_home
        else:
            # For totals: model and sharp should agree on direction
            model_over = model_line > market_line
            sharp_over = sharp_line > market_line
            return model_over == sharp_over

    def _get_market_probability(
        self,
        bet_type: BetType,
        market_odds: MarketOdds,
        pick: Pick,
    ) -> float:
        """Get implied probability from market odds."""
        def american_to_prob(odds: int) -> float:
            if odds < 0:
                return abs(odds) / (abs(odds) + 100)
            else:
                return 100 / (odds + 100)

        if bet_type == BetType.SPREAD:
            odds = market_odds.spread_price or -110
            return american_to_prob(odds)
        elif bet_type == BetType.SPREAD_1H:
            odds = market_odds.spread_price_1h or -110
            return american_to_prob(odds)
        elif bet_type == BetType.TOTAL:
            odds = (market_odds.over_price if pick == Pick.OVER else market_odds.under_price) or -110
            return american_to_prob(odds)
        elif bet_type == BetType.TOTAL_1H:
            odds = (market_odds.over_price_1h if pick == Pick.OVER else market_odds.under_price_1h) or -110
            return american_to_prob(odds)
        else:
            return 0.5


# ═══════════════════════════════════════════════════════════════════════════════
# Singleton instance for use throughout the application
# ═══════════════════════════════════════════════════════════════════════════════

prediction_engine_v33 = PredictionEngineV33()
