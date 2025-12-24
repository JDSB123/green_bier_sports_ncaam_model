from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from app.predictors.base import BasePredictor, MarketPrediction

if TYPE_CHECKING:
    from app.models import TeamRatings

@dataclass
class FHSpreadFactors:
    hca_base: float = 1.5  # Half of full game
    # Scaled factors

class FHSpreadIndependentModel(BasePredictor):
    MODEL_NAME = "FHSpreadIndependent"
    MODEL_VERSION = "1.0.0"
    MARKET_TYPE = "fh_spread"

    def predict(
        self,
        home: "TeamRatings",
        away: "TeamRatings",
        is_neutral: bool = False,
        home_rest_days: Optional[int] = None,
        away_rest_days: Optional[int] = None,
    ) -> MarketPrediction:
        # FH-specific spread logic
        pass

# Singleton
fh_spread_model = FHSpreadIndependentModel()