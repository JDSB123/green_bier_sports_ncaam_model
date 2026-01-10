"""
Machine Learning Module for NCAAM Predictions.

This module provides:
- Feature engineering from Barttorvik ratings and market data
- XGBoost classification models for bet outcomes
- Time-series cross-validation for proper backtesting
- Leakage-free training pipeline
- Production model loading and inference

Models trained:
- FG Spread: P(home covers)
- FG Total: P(over hits)
- 1H Spread: P(home covers 1H)
- 1H Total: P(over hits 1H)

v35.0.0 Updates:
- Added ProductionModelLoader for loading trained models
- Added enhance_prediction_with_ml for hybrid predictions
- Walk-forward validation framework support
"""

from app.ml.features import FeatureEngineer
from app.ml.models import BetPredictionModel, ModelRegistry

# Training pipeline (optional, may not be available in production)
try:
    from app.ml.training import TrainingPipeline
    HAS_TRAINING = True
except ImportError:
    TrainingPipeline = None
    HAS_TRAINING = False

# Production model loader
try:
    from app.ml.model_loader import (
        ProductionModelLoader,
        get_model_manager,
        reload_models,
        enhance_prediction_with_ml,
        ModelInfo,
        PredictionResult,
    )
    HAS_MODEL_LOADER = True
except ImportError:
    ProductionModelLoader = None
    get_model_manager = None
    reload_models = None
    enhance_prediction_with_ml = None
    ModelInfo = None
    PredictionResult = None
    HAS_MODEL_LOADER = False

__all__ = [
    # Core components
    "FeatureEngineer",
    "BetPredictionModel",
    "ModelRegistry",
    # Training (optional)
    "TrainingPipeline",
    "HAS_TRAINING",
    # Production model loading
    "ProductionModelLoader",
    "get_model_manager",
    "reload_models",
    "enhance_prediction_with_ml",
    "ModelInfo",
    "PredictionResult",
    "HAS_MODEL_LOADER",
]
