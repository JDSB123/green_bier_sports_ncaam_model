"""app.predictors

All 4 markets are designed to be independent and backtested:
- FG Spread (HCA tuned from historical results)
- FG Total (calibration tuned from historical results)
- 1H Spread (HCA tuned from historical results)
- 1H Total (calibration tuned from historical results)

Notes:
- Model versions are sourced from the service VERSION via app.__version__.
- Calibration constants are periodically re-fit/recalibrated; refer to each
    model class for the current constants.
"""

# Import base classes first (no circular dependencies)
from app.predictors.base import BasePredictor, MarketPrediction

# Import all market-specific models
from app.predictors.fg_spread import FGSpreadModel, fg_spread_model
from app.predictors.fg_total import FGTotalModel, fg_total_model
from app.predictors.h1_spread import H1SpreadModel, h1_spread_model
from app.predictors.h1_total import H1TotalModel, h1_total_model

__all__ = [
    # Base classes
    "BasePredictor",
    "MarketPrediction",
    # Model classes
    "FGSpreadModel",
    "FGTotalModel",
    "H1SpreadModel",
    "H1TotalModel",
    # Singleton instances
    "fg_spread_model",
    "fg_total_model",
    "h1_spread_model",
    "h1_total_model",
]
