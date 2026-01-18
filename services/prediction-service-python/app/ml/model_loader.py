"""
Production Model Loader

Loads trained ML models for use in production predictions.
Falls back to formula-based predictions if models not available.

CRITICAL: Models are trained with walk-forward validation to prevent leakage.

Usage:
    from app.ml.model_loader import get_model_manager

    manager = get_model_manager()

    # Get prediction for a game
    result = manager.predict_spread(game_features)

    # Get probability of bet winning
    proba = manager.get_bet_probability("fg_spread", features)
"""

import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Optional imports
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False
    logger.warning("XGBoost not installed. ML models will not be available.")


@dataclass
class ModelInfo:
    """Information about a loaded model."""
    model_type: str
    version: str
    is_available: bool
    accuracy: float
    auc_roc: float
    feature_count: int
    training_samples: int


@dataclass
class PredictionResult:
    """Result from ML model prediction."""
    market: str
    probability: float  # P(bet wins)
    confidence: str  # "high", "medium", "low"
    model_used: str  # "ml" or "formula"
    edge_adjustment: float  # Adjustment to formula-based prediction


class ProductionModelLoader:
    """
    Loads and manages trained ML models in production.

    Provides:
    1. Model loading from disk
    2. Fallback to formula-based predictions
    3. Probability calibration
    4. Ensemble predictions (optional)
    """

    # Market types
    MARKETS = ["fg_spread", "fg_total", "h1_spread", "h1_total"]

    def __init__(
        self,
        models_dir: Path | None = None,
        use_ml_models: bool = True,
        fallback_to_formula: bool = True,
    ):
        """
        Initialize the production model loader.

        Args:
            models_dir: Directory containing trained models
            use_ml_models: Whether to try loading ML models
            fallback_to_formula: Fall back to formula if ML not available
        """
        self.use_ml_models = use_ml_models and HAS_XGBOOST and HAS_NUMPY
        self.fallback_to_formula = fallback_to_formula

        # Set models directory
        if models_dir:
            self.models_dir = Path(models_dir)
        else:
            # Try multiple locations
            possible_dirs = [
                Path("/app/models"),  # Docker container
                Path(__file__).parent / "trained_models",  # Local dev/prod-relative
            ]

            for dir_path in possible_dirs:
                if dir_path.exists():
                    self.models_dir = dir_path
                    break
            else:
                self.models_dir = possible_dirs[0]  # Default to container path

        # Model storage
        self._models: dict[str, Any] = {}
        self._feature_names: dict[str, list[str]] = {}
        self._metadata: dict[str, dict] = {}

        # Load models on init
        if self.use_ml_models:
            self._load_all_models()

    def _load_all_models(self):
        """Load all available models."""
        for market in self.MARKETS:
            try:
                self._load_model(market)
            except Exception as e:
                logger.warning(f"Could not load model for {market}: {e}")

    def _load_model(self, market: str) -> bool:
        """
        Load a single model from disk.

        Returns True if successful.
        """
        model_path = self.models_dir / f"{market}_model_latest.pkl"

        if not model_path.exists():
            logger.info(f"No model file found for {market} at {model_path}")
            return False

        try:
            with open(model_path, 'rb') as f:
                data = pickle.load(f)

            self._models[market] = data.get("model")
            self._feature_names[market] = data.get("feature_names", [])
            self._metadata[market] = data.get("metadata", {})

            logger.info(
                f"Loaded {market} model",
                version=self._metadata[market].get("version", "unknown"),
                features=len(self._feature_names[market])
            )

            return True

        except Exception as e:
            logger.error(f"Error loading {market} model: {e}")
            return False

    def is_model_available(self, market: str) -> bool:
        """Check if a model is available for a market."""
        return market in self._models and self._models[market] is not None

    def get_model_info(self, market: str) -> ModelInfo | None:
        """Get information about a loaded model."""
        if not self.is_model_available(market):
            return ModelInfo(
                model_type=market,
                version="N/A",
                is_available=False,
                accuracy=0.0,
                auc_roc=0.0,
                feature_count=0,
                training_samples=0
            )

        meta = self._metadata.get(market, {})

        return ModelInfo(
            model_type=market,
            version=meta.get("version", "unknown"),
            is_available=True,
            accuracy=meta.get("accuracy", 0.0),
            auc_roc=meta.get("auc_roc", 0.0),
            feature_count=len(self._feature_names.get(market, [])),
            training_samples=meta.get("training_samples", 0)
        )

    def get_required_features(self, market: str) -> list[str]:
        """Get the required feature names for a market model."""
        return self._feature_names.get(market, [])

    def predict_probability(
        self,
        market: str,
        features: dict[str, float],
    ) -> PredictionResult:
        """
        Predict the probability that a bet will win.

        Args:
            market: Market type (fg_spread, fg_total, etc.)
            features: Dictionary of feature values

        Returns:
            PredictionResult with probability and confidence
        """
        # Check if ML model is available
        if self.is_model_available(market):
            try:
                proba = self._predict_with_ml(market, features)
                confidence = self._get_confidence_level(proba)

                # Calculate edge adjustment from probability
                # proba > 0.5 means more confident in bet winning
                edge_adjustment = (proba - 0.5) * 5.0  # Scale to ~2.5 pts max

                return PredictionResult(
                    market=market,
                    probability=proba,
                    confidence=confidence,
                    model_used="ml",
                    edge_adjustment=round(edge_adjustment, 2)
                )
            except Exception as e:
                logger.warning(f"ML prediction failed for {market}: {e}")
                if not self.fallback_to_formula:
                    raise

        # Fall back to formula-based
        if self.fallback_to_formula:
            return self._predict_with_formula(market, features)

        raise ValueError(f"No model available for {market} and fallback disabled")

    def _predict_with_ml(
        self,
        market: str,
        features: dict[str, float]
    ) -> float:
        """Make prediction using ML model."""
        model = self._models[market]
        feature_names = self._feature_names[market]

        # Build feature vector in correct order
        feature_vector = []
        for name in feature_names:
            value = features.get(name, 0.0)
            if value is None or (isinstance(value, float) and np.isnan(value)):
                value = 0.0
            feature_vector.append(value)

        # Make prediction
        X = np.array([feature_vector])
        proba = model.predict_proba(X)[0][1]

        # Clip to reasonable range
        proba = np.clip(proba, 0.15, 0.85)

        return float(proba)

    def _predict_with_formula(
        self,
        market: str,
        features: dict[str, float]
    ) -> PredictionResult:
        """Make prediction using formula-based approach."""
        # Default probability (50%)
        proba = 0.50

        # Get efficiency differential
        home_adj_o = features.get("home_adj_o", 105)
        home_adj_d = features.get("home_adj_d", 105)
        away_adj_o = features.get("away_adj_o", 105)
        away_adj_d = features.get("away_adj_d", 105)

        home_net = home_adj_o - home_adj_d
        away_net = away_adj_o - away_adj_d
        diff = home_net - away_net

        # Convert differential to probability
        # Rough approximation: 10 point net diff ~ 60% win probability
        proba = 0.5 + (diff / 100.0)
        proba = max(0.35, min(0.65, proba))

        return PredictionResult(
            market=market,
            probability=proba,
            confidence=self._get_confidence_level(proba),
            model_used="formula",
            edge_adjustment=0.0
        )

    def _get_confidence_level(self, proba: float) -> str:
        """Convert probability to confidence level."""
        deviation = abs(proba - 0.5)

        if deviation > 0.15:
            return "high"
        if deviation > 0.08:
            return "medium"
        return "low"

    def get_all_model_info(self) -> dict[str, ModelInfo]:
        """Get info for all models."""
        return {
            market: self.get_model_info(market)
            for market in self.MARKETS
        }


# Singleton instance
_model_manager: ProductionModelLoader | None = None


def get_model_manager() -> ProductionModelLoader:
    """Get the singleton model manager."""
    global _model_manager
    if _model_manager is None:
        _model_manager = ProductionModelLoader()
    return _model_manager


def reload_models():
    """Reload all models (useful after model updates)."""
    global _model_manager
    _model_manager = ProductionModelLoader()
    return _model_manager


# Integration with existing predictors
def enhance_prediction_with_ml(
    market: str,
    formula_prediction: float,
    game_features: dict[str, float]
) -> tuple[float, float, str]:
    """
    Enhance a formula-based prediction with ML probability.

    Args:
        market: Market type
        formula_prediction: The line from formula-based model
        game_features: Feature dictionary

    Returns:
        Tuple of (adjusted_prediction, probability, model_used)
    """
    manager = get_model_manager()

    try:
        result = manager.predict_probability(market, game_features)

        # Adjust prediction based on ML probability
        adjusted = formula_prediction + result.edge_adjustment

        return adjusted, result.probability, result.model_used

    except Exception as e:
        logger.warning(f"ML enhancement failed: {e}")
        return formula_prediction, 0.5, "formula"


if __name__ == "__main__":
    # Test the model loader
    print("=" * 60)
    print("Production Model Loader Test")
    print("=" * 60)

    manager = ProductionModelLoader()

    print("\nModel Status:")
    for market, info in manager.get_all_model_info().items():
        print(f"  {market}:")
        print(f"    Available: {info.is_available}")
        if info.is_available:
            print(f"    Version: {info.version}")
            print(f"    Accuracy: {info.accuracy:.3f}")
            print(f"    AUC-ROC: {info.auc_roc:.3f}")
            print(f"    Features: {info.feature_count}")

    # Test prediction
    test_features = {
        "home_adj_o": 115.0,
        "home_adj_d": 100.0,
        "away_adj_o": 108.0,
        "away_adj_d": 105.0,
        "home_tempo": 68.0,
        "away_tempo": 66.0,
    }

    print("\nTest Prediction (fg_spread):")
    result = manager.predict_probability("fg_spread", test_features)
    print(f"  Probability: {result.probability:.3f}")
    print(f"  Confidence: {result.confidence}")
    print(f"  Model Used: {result.model_used}")
    print(f"  Edge Adjustment: {result.edge_adjustment:+.2f}")
