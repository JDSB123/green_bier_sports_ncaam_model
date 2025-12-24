from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from app.predictors.base import BasePredictor, MarketPrediction

if TYPE_CHECKING:
    from app.models import TeamRatings

@dataclass
class FHAdjustmentFactors:
    base_calibration: float = 0.0
    tempo_high_threshold: float = 35.0  # Half of full game
    tempo_low_threshold: float = 33.0
    tempo_adj_per_point: float = 0.15
    barthag_diff_threshold: float = 0.15
    quality_adj_factor: float = 1.0
    three_pt_high_threshold: float = 19.0
    three_pt_adj_factor: float = 0.075
    eff_high_threshold: float = 57.5
    eff_low_threshold: float = 50.0
    eff_adj_factor: float = 0.1

class FHTotalIndependentModel(BasePredictor):
    MODEL_NAME = "FHTotalIndependent"
    MODEL_VERSION = "1.0.0"
    MARKET_TYPE = "fh_total"

    BASE_VARIANCE: float = 10.0
    MIN_EDGE: float = 1.0
    MAX_EDGE: float = 3.0
    OPTIMAL_EDGE: float = 2.0

    def __init__(self):
        self.factors = FHAdjustmentFactors()

    def _calculate_base_total(
        self,
        home: "TeamRatings",
        away: "TeamRatings",
        is_neutral: bool = False,
    ) -> tuple[float, float, float]:
        avg_tempo = self.calculate_expected_tempo(home, away) / 2  # FH adjustment

        home_eff = (home.adj_o + away.adj_d - self.LEAGUE_AVG_EFFICIENCY) * 0.95  # FH efficiency slight reduction
        away_eff = (away.adj_o + home.adj_d - self.LEAGUE_AVG_EFFICIENCY) * 0.95

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
        adjustment = 0.0
        reasons = []

        avg_tempo = (home.tempo + away.tempo) / 4  # FH tempo

        if avg_tempo > self.factors.tempo_high_threshold:
            tempo_adj = (avg_tempo - self.factors.tempo_high_threshold) * self.factors.tempo_adj_per_point
            adjustment += tempo_adj
            reasons.append(f"fast tempo +{tempo_adj:.1f}")

        # Similar logic for other adjustments, scaled for FH

        reasoning = ", ".join(reasons) if reasons else "standard"
        return adjustment, reasoning

    # Add other methods similarly scaled for FH

    def predict(
        self,
        home: "TeamRatings",
        away: "TeamRatings",
        is_neutral: bool = False,
        home_rest_days: Optional[int] = None,
        away_rest_days: Optional[int] = None,
    ) -> MarketPrediction:
        # Implement FH-specific prediction
        pass

# Singleton
fh_total_model = FHTotalIndependentModel()