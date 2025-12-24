"""
Modular Prediction Models v33.2

SPREAD MODELS ONLY (Proven with z=3.94 edge)

Each spread model (FG Spread, 1H Spread) has its own
independent calibration with:
- Market-validated parameters
- Tailored formulas
- Independent validation metrics

TOTAL MODELS: Not included - requires open source research
for proven approaches. See GitHub issues for progress.
"""

# Import base classes first (no circular dependencies)
from app.predictors.base import BasePredictor, MarketPrediction

# Import market-specific models (SPREADS ONLY)
from app.predictors.fg_spread import FGSpreadModel, fg_spread_model
from app.predictors.h1_spread import H1SpreadModel, h1_spread_model

__all__ = [
    # Base classes
    "BasePredictor",
    "MarketPrediction",
    # Model classes (SPREADS ONLY)
    "FGSpreadModel",
    "H1SpreadModel",
    # Singleton instances
    "fg_spread_model",
    "h1_spread_model",
]
