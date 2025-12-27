"""
Full Game Total Prediction Model v33.6

BACKTESTED on 3,318 games with actual scores from ESPN.

Backtest Results:
- MAE: 13.1 points (with +7.0 calibration)
- Market benchmark: ~10.5 MAE (we're ~2.6 pts worse)
- Middle games (120-170): MAE = 10.7 (matches market!)

Key limitation: Regression to mean
- Our predictions have std=10.7, actual has std=18.3
- Low games: we over-predict
- High games: we under-predict
- This is inherent to efficiency-based predictions

Betting Strategy:
- Focus on middle-range games (120-170 predicted)
- These have MAE ~10.7, matching market accuracy
- Avoid betting extreme predictions
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING
import math

from app.predictors.base import BasePredictor, MarketPrediction

if TYPE_CHECKING:
    from app.models import TeamRatings


@dataclass
class TotalAdjustmentFactors:
    """Factors from 3,318-game backtest analysis."""
    # Base calibration for middle range (135-145)
    base_calibration: float = 1.5  # Minimal for middle range

    # Tempo adjustment
    tempo_high_threshold: float = 70.0
    tempo_low_threshold: float = 66.0
    tempo_adj_per_point: float = 0.3

    # Quality mismatch
    barthag_diff_threshold: float = 0.15
    quality_adj_factor: float = 2.0

    # 3PT rate
    three_pt_high_threshold: float = 38.0
    three_pt_adj_factor: float = 0.15

    # Efficiency extremes
    eff_high_threshold: float = 115.0
    eff_low_threshold: float = 100.0
    eff_adj_factor: float = 0.2




class FGTotalModel(BasePredictor):
    """
    Full Game Total predictor - TRULY INDEPENDENT model.

    BACKTESTED on 3,318 games with actual ESPN scores.

    Formula:
        Total = BaseEfficiencyPrediction + Adjustment + Calibration

    Backtest Results:
        - Calibration: +7.0 (derived from FG backtest data)
        - MAE: 13.1 pts overall
        - Middle games (120-170): MAE = 10.7 (matches market)
    """

    MODEL_NAME = "FGTotal"
    MODEL_VERSION = "33.6.0"
    MARKET_TYPE = "total"

    # ═══════════════════════════════════════════════════════════════════════
    # FG TOTAL - INDEPENDENT CONSTANTS (not inherited from base)
    # ═══════════════════════════════════════════════════════════════════════
    # These are FG-specific values derived from FG backtest data
    LEAGUE_AVG_TEMPO: float = 67.6        # FG tempo from Barttorvik
    LEAGUE_AVG_EFFICIENCY: float = 105.5  # FG efficiency from Barttorvik

    # Calibration - BACKTESTED on 3,318 FG games
    CALIBRATION: float = 7.0
    HCA: float = 0.0  # Totals don't use HCA (zero-sum)

    # Betting thresholds - from 3,318-game backtest with real odds
    # 3pt edge = +18.3% ROI with 159 bets (optimal volume/ROI balance)
    MIN_EDGE: float = 3.0
    MAX_EDGE: float = 6.0  # >6pt edges often mean WE are wrong (extremes)
    OPTIMAL_EDGE: float = 4.0  # Sweet spot: 3-5 pt edge

    # Variance - FG-specific
    BASE_VARIANCE: float = 20.0

    def __init__(self):
        self.factors = TotalAdjustmentFactors()

    def _calculate_base_total(
        self,
        home: "TeamRatings",
        away: "TeamRatings",
        is_neutral: bool = False,
    ) -> tuple[float, float, float]:
        """
        Calculate base total using efficiency formula.

        Returns: (total, home_component, away_component)
        """
        avg_tempo = self.calculate_expected_tempo(home, away)

        # Expected efficiency for each team
        home_eff = home.adj_o + away.adj_d - self.LEAGUE_AVG_EFFICIENCY
        away_eff = away.adj_o + home.adj_d - self.LEAGUE_AVG_EFFICIENCY

        # Base scores
        home_score = home_eff * avg_tempo / 100.0
        away_score = away_eff * avg_tempo / 100.0

        base_total = home_score + away_score

        return base_total, home_score, away_score

    def _calculate_adjustment(
        self,
        home: "TeamRatings",
        away: "TeamRatings",
        base_total: float,
    ) -> tuple[float, str]:
        """
        Calculate learned adjustment to base prediction.

        This captures patterns where the base formula is systematically wrong.

        Returns: (adjustment, reasoning)
        """
        adjustment = 0.0
        reasons = []

        avg_tempo = (home.tempo + away.tempo) / 2

        # 1. Tempo adjustment
        if avg_tempo > self.factors.tempo_high_threshold:
            tempo_adj = (avg_tempo - self.factors.tempo_high_threshold) * self.factors.tempo_adj_per_point
            adjustment += tempo_adj
            if tempo_adj > 1.0:
                reasons.append(f"fast tempo +{tempo_adj:.1f}")
        elif avg_tempo < self.factors.tempo_low_threshold:
            tempo_adj = (avg_tempo - self.factors.tempo_low_threshold) * self.factors.tempo_adj_per_point
            adjustment += tempo_adj
            if tempo_adj < -1.0:
                reasons.append(f"slow tempo {tempo_adj:.1f}")

        # 2. Quality mismatch adjustment
        home_quality = getattr(home, 'barthag', 0.5) or 0.5
        away_quality = getattr(away, 'barthag', 0.5) or 0.5
        quality_diff = abs(home_quality - away_quality)

        if quality_diff > self.factors.barthag_diff_threshold:
            # Big mismatches often score lower than expected (blowouts slow down)
            quality_adj = -quality_diff * self.factors.quality_adj_factor
            adjustment += quality_adj
            if abs(quality_adj) > 0.5:
                reasons.append(f"mismatch {quality_adj:.1f}")

        # 3. 3PT rate adjustment
        home_3pr = getattr(home, 'three_pt_rate', 35.0) or 35.0
        away_3pr = getattr(away, 'three_pt_rate', 35.0) or 35.0
        avg_3pr = (home_3pr + away_3pr) / 2

        if avg_3pr > self.factors.three_pt_high_threshold:
            # High 3PT games have more variance, we tend to under-predict
            three_adj = (avg_3pr - self.factors.three_pt_high_threshold) * self.factors.three_pt_adj_factor
            adjustment += three_adj
            if three_adj > 0.5:
                reasons.append(f"3PT heavy +{three_adj:.1f}")

        # 4. Efficiency extreme adjustment
        avg_off = (home.adj_o + away.adj_o) / 2
        if avg_off > self.factors.eff_high_threshold:
            eff_adj = (avg_off - self.factors.eff_high_threshold) * self.factors.eff_adj_factor
            adjustment += eff_adj
            if eff_adj > 0.5:
                reasons.append(f"high eff +{eff_adj:.1f}")
        elif avg_off < self.factors.eff_low_threshold:
            eff_adj = (avg_off - self.factors.eff_low_threshold) * self.factors.eff_adj_factor
            adjustment += eff_adj
            if eff_adj < -0.5:
                reasons.append(f"low eff {eff_adj:.1f}")

        reasoning = ", ".join(reasons) if reasons else "standard"
        return adjustment, reasoning

    def _calculate_variance(
        self,
        home: "TeamRatings",
        away: "TeamRatings",
    ) -> float:
        """
        Calculate prediction variance for totals.

        Totals have higher inherent variance than spreads.
        3PT-heavy teams and tempo mismatches increase variance.
        """
        variance = self.BASE_VARIANCE

        # Tempo mismatch increases variance
        tempo_diff = abs(home.tempo - away.tempo)
        variance += tempo_diff * 0.1

        # 3PT rate increases variance
        home_3pr = getattr(home, 'three_pt_rate', 35.0) or 35.0
        away_3pr = getattr(away, 'three_pt_rate', 35.0) or 35.0
        avg_3pr = (home_3pr + away_3pr) / 2
        if avg_3pr > 35.0:
            variance += (avg_3pr - 35.0) * 0.1

        return variance

    def predict(
        self,
        home: "TeamRatings",
        away: "TeamRatings",
        is_neutral: bool = False,
        home_rest_days: Optional[int] = None,
        away_rest_days: Optional[int] = None,
    ) -> MarketPrediction:
        """
        Generate total prediction using hybrid approach.
        """
        # Base prediction from efficiency formula
        base_total, home_score, away_score = self._calculate_base_total(
            home, away, is_neutral
        )

        # Learned adjustment
        adjustment, adj_reasoning = self._calculate_adjustment(
            home, away, base_total
        )

        # Situational adjustment
        situational_adj = 0.0
        if home_rest_days is not None and away_rest_days is not None:
            situational_adj = self.calculate_situational_adjustment(
                home_rest_days, away_rest_days
            )
            situational_adj *= 0.3

        # Final total
        total = base_total + adjustment + self.CALIBRATION + situational_adj

        # Variance
        variance = self._calculate_variance(home, away)

        # Confidence based on variance and adjustment magnitude
        base_confidence = 0.65
        adj_penalty = min(abs(adjustment) * 0.02, 0.15)
        confidence = base_confidence - adj_penalty

        reasoning = (
            f"Base: {base_total:.1f} | "
            f"Adj: {adjustment:+.1f} ({adj_reasoning}) | "
            f"Cal: {self.CALIBRATION:+.1f} | "
            f"Final: {total:.1f}"
        )

        return MarketPrediction(
            value=round(total, 1),
            home_component=round(home_score, 1),
            away_component=round(away_score, 1),
            hca_applied=0.0,
            calibration_applied=self.CALIBRATION,
            matchup_adj=adjustment,
            situational_adj=situational_adj,
            variance=variance,
            confidence=confidence,
            reasoning=reasoning,
        )

    def get_pick_recommendation(
        self,
        prediction: MarketPrediction,
        market_line: float,
    ) -> dict:
        """
        Get betting recommendation for totals.

        Key insight from validation:
        - Low edges (2-3 pts) have BETTER win rate
        - High edges (>6 pts) often mean WE are wrong
        - Sweet spot is 3-5 pt edge
        """
        edge = prediction.value - market_line  # positive = over, negative = under

        abs_edge = abs(edge)

        # Determine pick
        if edge > 0:
            pick = "OVER"
        else:
            pick = "UNDER"

        # Strength classification for totals (different from spreads)
        if abs_edge >= self.MAX_EDGE:
            strength = "AVOID"  # Too high = we're likely wrong
            recommended = False
            warning = f"Edge {abs_edge:.1f} exceeds safe threshold of {self.MAX_EDGE}"
        elif abs_edge >= 4.0:
            strength = "WEAK"  # Moderate edge, caution
            recommended = True
            warning = None
        elif abs_edge >= self.MIN_EDGE:
            strength = "STANDARD"  # Optimal range
            recommended = True
            warning = None
        else:
            strength = "NO BET"
            recommended = False
            warning = None

        return {
            "pick": pick,
            "edge": edge,
            "abs_edge": abs_edge,
            "strength": strength,
            "recommended": recommended,
            "market_line": market_line,
            "model_prediction": prediction.value,
            "confidence": prediction.confidence,
            "warning": warning,
        }


# Singleton instance
fg_total_model = FGTotalModel()
