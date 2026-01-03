"""
Machine Learning Module for NCAAM Predictions.

This module provides:
- Feature engineering from Barttorvik ratings and market data
- XGBoost classification models for bet outcomes
- Time-series cross-validation for proper backtesting
- Leakage-free training pipeline

Models trained:
- FG Spread: P(home covers)
- FG Total: P(over hits)
- 1H Spread: P(home covers 1H)
- 1H Total: P(over hits 1H)
"""

from app.ml.features import FeatureEngineer
from app.ml.models import BetPredictionModel, ModelRegistry
from app.ml.training import TrainingPipeline

__all__ = [
    "FeatureEngineer",
    "BetPredictionModel",
    "ModelRegistry",
    "TrainingPipeline",
]
