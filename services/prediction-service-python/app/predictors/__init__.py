"""
Modular Prediction Models v33.6

All 4 markets are TRULY INDEPENDENT & BACKTESTED:
- FG Spread: HCA=5.8 (from 3,318-game backtest, MAE=10.57)
- FG Total: Calibration=+7.0 (from 3,318-game backtest, MAE=13.1)
- 1H Spread: HCA=3.6 (from 904-game 1H backtest, MAE=8.25)
- 1H Total: Calibration=+2.7 (from 562-game 1H backtest, MAE=8.88)

All calibrations derived from real ESPN game data.
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
