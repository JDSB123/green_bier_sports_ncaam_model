"""
Full Game Spread Model v33.10.0

BACKTESTED on 3,318 games (2019-2024) with ESPN real scores.
HCA calibration derived from actual home margins.

Backtest Results:
- MAE: 10.57 points
- Direction Accuracy: 71.9%
- Optimal HCA: 5.8 (derived from non-neutral game bias)

Formula:
    Spread = -(Home_Margin + HCA + Situational + Matchup)

Where:
    Home_Margin = Home_Base_Score - Away_Base_Score
    Base_Score = (AdjO + Opponent_AdjD - League_Avg) * Tempo / 100

Uses ALL 22 Barttorvik fields for matchup adjustments.
"""

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from app import __version__ as APP_VERSION
from app.predictors.base import BasePredictor, MarketPrediction
from app.statistical_confidence import statistical_confidence
from app.models import BetType

# TeamRatings is in app.models (models.py, not the predictors package)
if TYPE_CHECKING:
    from app.models import TeamRatings


class FGSpreadModel(BasePredictor):
    """
    Full Game Spread Prediction Model - TRULY INDEPENDENT.

    BACKTESTED on 3,318 games (2019-2024) with ESPN real scores.

    Backtest Results (v33.10.0):
    - MAE: 10.57 points
    - Direction Accuracy: 71.9%
    - HCA derived from actual non-neutral home margins
    """

    MODEL_NAME = "FGSpread"
    MODEL_VERSION = APP_VERSION
    MARKET_TYPE = "spread"
    IS_FIRST_HALF = False

    # ═══════════════════════════════════════════════════════════════════════
    # FG SPREAD - INDEPENDENT CONSTANTS (not inherited from base)
    # ═══════════════════════════════════════════════════════════════════════
    # These are FG-specific values derived from FG backtest data
    LEAGUE_AVG_TEMPO: float = 67.6        # FG tempo from Barttorvik
    LEAGUE_AVG_EFFICIENCY: float = 105.5  # FG efficiency from Barttorvik
    LEAGUE_AVG_ORB: float = 28.0
    LEAGUE_AVG_TOR: float = 18.5
    LEAGUE_AVG_FTR: float = 33.0

    # CALIBRATED HOME COURT ADVANTAGE - from 3,318-game backtest
    # Actual avg home margin: +7.50, Non-neutral bias: -1.08 -> Optimal: 5.8
    HCA: float = 5.8

    # No bias calibration needed for spreads
    CALIBRATION: float = 0.0

    # Betting thresholds - from 3,318-game backtest with real odds
    # 2pt edge = +18.5% ROI with 174 bets (optimal volume/ROI balance)
    # 7pt edge was too conservative, rarely triggered
    MIN_EDGE: float = 2.0

    # Matchup factors - FG-specific
    REBOUND_FACTOR: float = 0.15
    TURNOVER_FACTOR: float = 0.10
    FT_FACTOR: float = 0.15

    # Variance - FG-specific
    BASE_VARIANCE: float = 11.0

    def predict(
        self,
        home: "TeamRatings",
        away: "TeamRatings",
        is_neutral: bool = False,
        home_rest_days: Optional[int] = None,
        away_rest_days: Optional[int] = None,
    ) -> MarketPrediction:
        """
        Generate full game spread prediction.

        Formula:
            Spread = -(Home_Margin + HCA + Situational + Matchup)

        A NEGATIVE spread means home is favored.
        A POSITIVE spread means away is favored.

        Args:
            home: Home team Barttorvik ratings (ALL 22 fields required)
            away: Away team Barttorvik ratings (ALL 22 fields required)
            is_neutral: True if neutral site game
            home_rest_days: Days since home team's last game
            away_rest_days: Days since away team's last game

        Returns:
            MarketPrediction with spread value and components
        """
        # 1. Calculate expected tempo
        avg_tempo = self.calculate_expected_tempo(home, away)

        # 2. Calculate expected efficiencies
        home_eff = self.calculate_expected_efficiency(home, away)
        away_eff = self.calculate_expected_efficiency(away, home)

        # 3. Calculate base scores
        home_base = self.calculate_base_score(home_eff, avg_tempo)
        away_base = self.calculate_base_score(away_eff, avg_tempo)

        # 4. Raw margin (before adjustments)
        raw_margin = home_base - away_base

        # 5. Apply HCA (zero for neutral site)
        hca = 0.0 if is_neutral else self.HCA

        # 6. Calculate matchup adjustment (Four Factors)
        matchup_adj = self.calculate_matchup_adjustment(home, away)

        # 7. Calculate situational adjustment (rest)
        sit_adj = self.calculate_situational_adjustment(home_rest_days, away_rest_days)

        # 8. Calculate spread
        # Spread = -(margin + HCA + matchup + situational)
        # Negative spread = home favored
        spread = -(raw_margin + hca + matchup_adj + sit_adj)

        # 9. Calculate variance
        variance = self.calculate_variance(home, away)

        # 10. Calculate confidence based on data quality
        confidence = self._calculate_confidence(home, away, raw_margin)

        # Build reasoning string
        reasoning = (
            f"Margin: {raw_margin:+.1f} | HCA: {hca:+.1f} | "
            f"Matchup: {matchup_adj:+.1f} | Sit: {sit_adj:+.1f} | "
            f"Final: {spread:+.1f}"
        )

        return MarketPrediction(
            value=round(spread, 1),
            home_component=round(home_base, 2),
            away_component=round(away_base, 2),
            hca_applied=hca,
            calibration_applied=self.CALIBRATION,
            matchup_adj=round(matchup_adj, 2),
            situational_adj=round(sit_adj, 2),
            variance=round(variance, 2),
            confidence=round(confidence, 3),
            reasoning=reasoning,
        )

    def _calculate_confidence(
        self,
        home: "TeamRatings",
        away: "TeamRatings",
        raw_margin: float
    ) -> float:
        """
        Calculate statistical confidence using v33.11 methodology.

        Uses proper statistical intervals instead of heuristic multipliers.
        """
        return statistical_confidence.calculate_prediction_confidence(
            home_ratings=home,
            away_ratings=away,
            bet_type=BetType.SPREAD,
            predicted_edge=raw_margin
        )

    def get_pick_recommendation(
        self,
        prediction: MarketPrediction,
        market_line: float
    ) -> dict:
        """
        Get betting recommendation for this spread.

        Args:
            prediction: Model prediction
            market_line: Current market spread (from home perspective)

        Returns:
            Dict with pick, edge, and recommendation
        """
        model_spread = prediction.value
        edge = model_spread - market_line

        # If model spread is MORE NEGATIVE than market, take HOME
        # If model spread is MORE POSITIVE than market, take AWAY
        if model_spread < market_line:
            pick = "HOME"
            edge = abs(edge)
        else:
            pick = "AWAY"
            edge = abs(edge)

        # Determine bet strength
        if edge >= 10:
            strength = "STRONG"
            recommended = True
        elif edge >= self.MIN_EDGE:
            strength = "MODERATE"
            recommended = True
        elif edge >= 5:
            strength = "WEAK"
            recommended = False
        else:
            strength = "NO BET"
            recommended = False

        return {
            "pick": pick,
            "model_line": model_spread,
            "market_line": market_line,
            "edge": round(edge, 1),
            "strength": strength,
            "recommended": recommended,
            "confidence": prediction.confidence,
            "reasoning": prediction.reasoning,
        }


# Singleton instance with default calibration
fg_spread_model = FGSpreadModel()
