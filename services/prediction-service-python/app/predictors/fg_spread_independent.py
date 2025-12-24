from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from app.predictors.base import BasePredictor, MarketPrediction

if TYPE_CHECKING:
    from app.models import TeamRatings

@dataclass
class FGSpreadFactors:
    hca_base: float = 3.0
    quality_threshold: float = 0.2
    quality_adj: float = 0.5
    # etc.

class FGSpreadIndependentModel(BasePredictor):
    MODEL_NAME = "FGSpreadIndependent"
    MODEL_VERSION = "1.0.0"
    MARKET_TYPE = "fg_spread"

    def predict(
        self,
        home: "TeamRatings",
        away: "TeamRatings",
        is_neutral: bool = False,
        home_rest_days: Optional[int] = None,
        away_rest_days: Optional[int] = None,
    ) -> MarketPrediction:
        # Independent spread calculation
        home_eff = home.adj_o - away.adj_d
        away_eff = away.adj_o - home.adj_d
        base_spread = (home_eff - away_eff) / 2 + self.factors.hca_base if not is_neutral else 0
        # Adjustments
        return MarketPrediction(value=base_spread, ...)

# Singleton
fg_spread_model = FGSpreadIndependentModel()