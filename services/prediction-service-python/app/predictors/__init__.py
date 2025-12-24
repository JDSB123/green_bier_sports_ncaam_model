"""
Modular Prediction Models v33.3

All 4 markets now have independent models:
- FG Spread: PROVEN edge (z=3.94), HCA=4.7
- FG Total: Hybrid approach (base + learned adjustment)
- 1H Spread: Independent, HCA=2.35
- 1H Total: Independent, calibration=-2.3

SPREADS: Statistically significant edge
TOTALS: Hybrid ML approach, use with caution on high edges
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
