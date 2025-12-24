from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from app.predictors.base import BasePredictor, MarketPrediction

if TYPE_CHECKING:
    from app.models import TeamRatings


@dataclass
class FGTotalFactors:
    base_calibration: float = 1.5
    tempo_high_threshold: float = 70.0
    tempo_low_threshold: float = 66.0
    tempo_adj_per_point: float = 0.3
    barthag_diff_threshold: float = 0.15
    quality_adj_factor: float = 2.0
    three_pt_high_threshold: float = 38.0
    three_pt_adj_factor: float = 0.15
    eff_high_threshold: float = 115.0
    eff_low_threshold: float = 100.0
    eff_adj_factor: float = 0.2


class IndependentFGTotalModel(BasePredictor):
    MODEL_NAME = "IndependentFGTotal"
    MODEL_VERSION = "1.0.0"
    MARKET_TYPE = "total"
    CALIBRATION = 7.0
    HCA = 0.0
    MIN_EDGE = 2.0
    MAX_EDGE = 6.0
    OPTIMAL_EDGE = 3.0
    BASE_VARIANCE = 20.0

    def __init__(self):
        self.factors = FGTotalFactors()

    def _calculate_base_total(self, home: TeamRatings, away: TeamRatings, is_neutral: bool = False) -> tuple[float, float, float]:
        avg_tempo = self.calculate_expected_tempo(home, away)
        home_eff = home.adj_o + away.adj_d - self.LEAGUE_AVG_EFFICIENCY
        away_eff = away.adj_o + home.adj_d - self.LEAGUE_AVG_EFFICIENCY
        home_score = home_eff * avg_tempo / 100.0
        away_score = away_eff * avg_tempo / 100.0
        base_total = home_score + away_score
        return base_total, home_score, away_score

    def _calculate_adjustment(self, home: TeamRatings, away: TeamRatings, base_total: float) -> tuple[float, str]:
        adjustment = 0.0
        reasons = []
        avg_tempo = (home.tempo + away.tempo) / 2

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

        home_quality = getattr(home, 'barthag', 0.5) or 0.5
        away_quality = getattr(away, 'barthag', 0.5) or 0.5
        quality_diff = abs(home_quality - away_quality)

        if quality_diff > self.factors.barthag_diff_threshold:
            quality_adj = -quality_diff * self.factors.quality_adj_factor
            adjustment += quality_adj
            if abs(quality_adj) > 0.5:
                reasons.append(f"mismatch {quality_adj:.1f}")

        home_3pr = getattr(home, 'three_pt_rate', 35.0) or 35.0
        away_3pr = getattr(away, 'three_pt_rate', 35.0) or 35.0
        avg_3pr = (home_3pr + away_3pr) / 2

        if avg_3pr > self.factors.three_pt_high_threshold:
            three_adj = (avg_3pr - self.factors.three_pt_high_threshold) * self.factors.three_pt_adj_factor
            adjustment += three_adj
            if three_adj > 0.5:
                reasons.append(f"3PT heavy +{three_adj:.1f}")

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

    def _calculate_variance(self, home: TeamRatings, away: TeamRatings) -> float:
        variance = self.BASE_VARIANCE
        tempo_diff = abs(home.tempo - away.tempo)
        variance += tempo_diff * 0.1
        home_3pr = getattr(home, 'three_pt_rate', 35.0) or 35.0
        away_3pr = getattr(away, 'three_pt_rate', 35.0) or 35.0
        avg_3pr = (home_3pr + away_3pr) / 2
        if avg_3pr > 35.0:
            variance += (avg_3pr - 35.0) * 0.1
        return variance

    def predict(self, home: TeamRatings, away: TeamRatings, is_neutral: bool = False, home_rest_days: Optional[int] = None, away_rest_days: Optional[int] = None) -> MarketPrediction:
        base_total, home_score, away_score = self._calculate_base_total(home, away, is_neutral)
        adjustment, adj_reasoning = self._calculate_adjustment(home, away, base_total)
        situational_adj = 0.0
        if home_rest_days is not None and away_rest_days is not None:
            situational_adj = self.calculate_situational_adjustment(home_rest_days, away_rest_days)
            situational_adj *= 0.3
        prelim_total = base_total + adjustment + situational_adj
        expanded_total = self._expand_prediction(prelim_total)
        expansion_adj = expanded_total - prelim_total
        total = expanded_total + self.CALIBRATION
        variance = self._calculate_variance(home, away)
        base_confidence = 0.65
        if prelim_total < 130 or prelim_total > 155:
            base_confidence = 0.55
        adj_penalty = min(abs(adjustment) * 0.02, 0.15)
        confidence = base_confidence - adj_penalty
        reasoning = f"Base: {base_total:.1f} | Adj: {adjustment:+.1f} ({adj_reasoning}) | Expand: {expansion_adj:+.1f} | Final: {total:.1f}"
        return MarketPrediction(
            value=round(total, 1),
            home_component=round(home_score, 1),
            away_component=round(away_score, 1),
            hca_applied=0.0,
            calibration_applied=expansion_adj,
            matchup_adj=adjustment,
            situational_adj=situational_adj,
            variance=variance,
            confidence=confidence,
            reasoning=reasoning,
        )

    def get_pick_recommendation(self, prediction: MarketPrediction, market_line: float) -> dict:
        edge = prediction.value - market_line
        abs_edge = abs(edge)
        pick = "OVER" if edge > 0 else "UNDER"
        if abs_edge >= self.MAX_EDGE:
            strength = "AVOID"
            recommended = False
            warning = f"Edge {abs_edge:.1f} exceeds safe threshold of {self.MAX_EDGE}"
        elif abs_edge >= 4.0:
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


independent_fg_total_model = IndependentFGTotalModel()
