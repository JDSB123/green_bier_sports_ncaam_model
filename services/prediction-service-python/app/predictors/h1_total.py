"""
First Half Total Prediction Model v33.3

Independent 1H total model (NOT scaled from FG).

Key findings:
- 1H totals are approximately 48% of FG totals (not 50%)
- First halves have different scoring patterns
- Higher variance than FG totals due to shorter sample
- Lines are "softer" - less sharp action on 1H markets

Betting Strategy:
- 1H total lines have more inefficiency
- Similar to FG: avoid very high edges
- Focus on low-to-moderate edge bets
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from app.predictors.base import BasePredictor, MarketPrediction

if TYPE_CHECKING:
    from app.models import TeamRatings


@dataclass
class H1TotalFactors:
    """First half specific factors."""
    # 1H is approximately 48% of FG (not 50% due to slower start)
    tempo_factor: float = 0.48

    # Calibration (50% of FG calibration)
    calibration: float = -2.3

    # Tempo thresholds for adjustment
    tempo_high_threshold: float = 70.0
    tempo_low_threshold: float = 66.0
    tempo_adj_per_point: float = 0.15  # Half of FG

    # Quality mismatch
    barthag_diff_threshold: float = 0.15
    quality_adj_factor: float = 1.0  # Half of FG


class H1TotalModel(BasePredictor):
    """
    First Half Total predictor.

    Uses independent calculation, not simply scaled from FG.
    """

    MODEL_NAME = "H1Total"
    MODEL_VERSION = "33.3.0"
    MARKET_TYPE = "total"

    # Calibration
    CALIBRATION: float = -2.3
    HCA: float = 0.0

    # Betting thresholds
    MIN_EDGE: float = 1.5  # Lower threshold for 1H
    MAX_EDGE: float = 4.0  # Lower than FG
    OPTIMAL_EDGE: float = 2.0

    # Higher variance for 1H
    BASE_VARIANCE: float = 8.0

    def __init__(self):
        self.factors = H1TotalFactors()

    def _calculate_base_total(
        self,
        home: "TeamRatings",
        away: "TeamRatings",
    ) -> tuple[float, float, float]:
        """Calculate base 1H total."""
        avg_tempo = self.calculate_expected_tempo(home, away)

        # Expected efficiency
        home_eff = home.adj_o + away.adj_d - self.LEAGUE_AVG_EFFICIENCY
        away_eff = away.adj_o + home.adj_d - self.LEAGUE_AVG_EFFICIENCY

        # 1H scores (scaled by tempo factor)
        home_score = home_eff * avg_tempo / 100.0 * self.factors.tempo_factor
        away_score = away_eff * avg_tempo / 100.0 * self.factors.tempo_factor

        base_total = home_score + away_score

        return base_total, home_score, away_score

    def _calculate_adjustment(
        self,
        home: "TeamRatings",
        away: "TeamRatings",
        base_total: float,
    ) -> tuple[float, str]:
        """Calculate 1H-specific adjustment."""
        adjustment = 0.0
        reasons = []

        avg_tempo = (home.tempo + away.tempo) / 2

        # Tempo adjustment (scaled for 1H)
        if avg_tempo > self.factors.tempo_high_threshold:
            tempo_adj = (avg_tempo - self.factors.tempo_high_threshold) * self.factors.tempo_adj_per_point
            adjustment += tempo_adj
            if tempo_adj > 0.5:
                reasons.append(f"fast +{tempo_adj:.1f}")
        elif avg_tempo < self.factors.tempo_low_threshold:
            tempo_adj = (avg_tempo - self.factors.tempo_low_threshold) * self.factors.tempo_adj_per_point
            adjustment += tempo_adj
            if tempo_adj < -0.5:
                reasons.append(f"slow {tempo_adj:.1f}")

        # Quality mismatch
        home_quality = getattr(home, 'barthag', 0.5) or 0.5
        away_quality = getattr(away, 'barthag', 0.5) or 0.5
        quality_diff = abs(home_quality - away_quality)

        if quality_diff > self.factors.barthag_diff_threshold:
            quality_adj = -quality_diff * self.factors.quality_adj_factor
            adjustment += quality_adj
            if abs(quality_adj) > 0.3:
                reasons.append(f"mismatch {quality_adj:.1f}")

        reasoning = ", ".join(reasons) if reasons else "standard"
        return adjustment, reasoning

    def _calculate_variance(
        self,
        home: "TeamRatings",
        away: "TeamRatings",
    ) -> float:
        """Calculate 1H variance (higher than FG)."""
        variance = self.BASE_VARIANCE

        # Tempo mismatch
        tempo_diff = abs(home.tempo - away.tempo)
        variance += tempo_diff * 0.08

        # 3PT rate
        home_3pr = getattr(home, 'three_pt_rate', 35.0) or 35.0
        away_3pr = getattr(away, 'three_pt_rate', 35.0) or 35.0
        avg_3pr = (home_3pr + away_3pr) / 2
        if avg_3pr > 35.0:
            variance += (avg_3pr - 35.0) * 0.08

        return variance

    def predict(
        self,
        home: "TeamRatings",
        away: "TeamRatings",
        is_neutral: bool = False,
        home_rest_days: Optional[int] = None,
        away_rest_days: Optional[int] = None,
    ) -> MarketPrediction:
        """Generate 1H total prediction."""
        base_total, home_score, away_score = self._calculate_base_total(home, away)

        adjustment, adj_reasoning = self._calculate_adjustment(
            home, away, base_total
        )

        situational_adj = 0.0
        if home_rest_days is not None and away_rest_days is not None:
            situational_adj = self.calculate_situational_adjustment(
                home_rest_days, away_rest_days
            ) * 0.15  # Minimal impact on 1H

        total = base_total + adjustment + self.CALIBRATION + situational_adj

        variance = self._calculate_variance(home, away)

        # Lower confidence for 1H
        confidence = 0.55 - min(abs(adjustment) * 0.02, 0.1)

        reasoning = (
            f"1H Base: {base_total:.1f} | "
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
        """Get 1H betting recommendation."""
        edge = prediction.value - market_line

        abs_edge = abs(edge)

        if edge > 0:
            pick = "OVER"
        else:
            pick = "UNDER"

        # 1H thresholds
        if abs_edge >= self.MAX_EDGE:
            strength = "AVOID"
            recommended = False
            warning = f"1H edge {abs_edge:.1f} exceeds {self.MAX_EDGE}"
        elif abs_edge >= 2.5:
            strength = "WEAK"
            recommended = True
            warning = None
        elif abs_edge >= self.MIN_EDGE:
            strength = "STANDARD"
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
h1_total_model = H1TotalModel()
