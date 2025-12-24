from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from app.predictors.base import BasePredictor, MarketPrediction

if TYPE_CHECKING:
    from app.models import TeamRatings


@dataclass
class FHSpreadFactors:
    base_hca: float = 1.5
    quality_threshold: float = 0.8
    quality_adj_factor: float = 0.75
    tempo_high_threshold: float = 35.0
    tempo_adj_factor: float = 0.25
    rest_diff_threshold: int = 3
    rest_adj_per_day: float = 0.5


class IndependentFHSpreadModel(BasePredictor):
    MODEL_NAME = "IndependentFHSpread"
    MODEL_VERSION = "1.0.0"
    MARKET_TYPE = "spread"
    CALIBRATION = 0.0
    MIN_EDGE = 0.75
    MAX_EDGE = 2.5
    OPTIMAL_EDGE = 1.25
    BASE_VARIANCE = 6.0

    def __init__(self):
        self.factors = FHSpreadFactors()

    def _calculate_base_spread(self, home: TeamRatings, away: TeamRatings, is_neutral: bool = False) -> tuple[float, float, float]:
        home_eff = (home.adj_o - away.adj_d) * 0.95
        away_eff = (away.adj_o - home.adj_d) * 0.95
        expected_margin = (home_eff - away_eff) / 2.0
        hca = self.factors.base_hca if not is_neutral else 0.0
        base_spread = expected_margin + hca
        return base_spread, expected_margin, hca

    def _calculate_adjustment(self, home: TeamRatings, away: TeamRatings) -> tuple[float, str]:
        adjustment = 0.0
        reasons = []

        home_quality = getattr(home, 'barthag', 0.5) or 0.5
        away_quality = getattr(away, 'barthag', 0.5) or 0.5
        if home_quality > self.factors.quality_threshold and away_quality < (1 - self.factors.quality_threshold):
            qual_adj = self.factors.quality_adj_factor
            adjustment += qual_adj
            reasons.append(f"home quality adv +{qual_adj:.1f}")

        avg_tempo = (home.tempo + away.tempo) / 4
        if avg_tempo > self.factors.tempo_high_threshold:
            tempo_adj = (avg_tempo - self.factors.tempo_high_threshold) * self.factors.tempo_adj_factor
            adjustment += tempo_adj / 2
            if tempo_adj > 0.5:
                reasons.append(f"high tempo +{tempo_adj / 2:.1f}")

        reasoning = ", ".join(reasons) if reasons else "standard"
        return adjustment, reasoning

    def _calculate_variance(self, home: TeamRatings, away: TeamRatings) -> float:
        variance = self.BASE_VARIANCE
        quality_diff = abs(home.barthag - away.barthag)
        variance += quality_diff * 2.5
        return variance

    def predict(self, home: TeamRatings, away: TeamRatings, is_neutral: bool = False, home_rest_days: Optional[int] = None, away_rest_days: Optional[int] = None) -> MarketPrediction:
        base_spread, margin, hca = self._calculate_base_spread(home, away, is_neutral)
        adjustment, adj_reasoning = self._calculate_adjustment(home, away)
        situational_adj = 0.0
        if home_rest_days is not None and away_rest_days is not None:
            rest_diff = home_rest_days - away_rest_days
            if abs(rest_diff) > self.factors.rest_diff_threshold:
                situational_adj = rest_diff * self.factors.rest_adj_per_day
        final_spread = base_spread + adjustment + situational_adj
        variance = self._calculate_variance(home, away)
        confidence = 0.7 - (abs(adjustment) * 0.025)
        reasoning = f"Base: {base_spread:.1f} | Adj: {adjustment:+.1f} ({adj_reasoning}) | Situational: {situational_adj:+.1f} | Final: {final_spread:.1f}"
        return MarketPrediction(
            value=round(final_spread, 1),
            home_component=round(margin + hca, 1),
            away_component=0.0,
            hca_applied=hca,
            calibration_applied=0.0,
            matchup_adj=adjustment,
            situational_adj=situational_adj,
            variance=variance,
            confidence=confidence,
            reasoning=reasoning,
        )

    def get_pick_recommendation(self, prediction: MarketPrediction, market_line: float) -> dict:
        edge = -prediction.value - market_line
        abs_edge = abs(edge)
        pick = "HOME" if edge < 0 else "AWAY"
        if abs_edge >= self.MAX_EDGE:
            strength = "STRONG"
            recommended = True
        elif abs_edge >= self.OPTIMAL_EDGE:
            strength = "STANDARD"
            recommended = True
        elif abs_edge >= self.MIN_EDGE:
            strength = "WEAK"
            recommended = True
        else:
            strength = "NO BET"
            recommended = False
        return {
            "pick": pick,
            "edge": edge,
            "abs_edge": abs_edge,
            "strength": strength,
            "recommended": recommended,
            "market_line": market_line,
            "model_prediction": prediction.value,
            "confidence": prediction.confidence,
        }


independent_fh_spread_model = IndependentFHSpreadModel()
