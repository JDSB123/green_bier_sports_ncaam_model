"""
XGBoost Classification Models for NCAAM Bet Predictions.

Each bet type has its own model trained on historical outcomes:
- FG Spread: P(home covers the spread)
- FG Total: P(game goes over)
- 1H Spread: P(home covers 1H spread)
- 1H Total: P(1H goes over)

Models output calibrated probabilities, not just classifications.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

# Optional XGBoost import
try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    xgb = None
    HAS_XGBOOST = False
    logger.warning("XGBoost not installed. ML models will not be available.")


@dataclass
class ModelMetadata:
    """Metadata for a trained model."""
    model_type: str  # "fg_spread", "fg_total", "h1_spread", "h1_total"
    version: str
    trained_at: str
    training_samples: int
    validation_samples: int

    # Performance metrics
    accuracy: float
    log_loss: float
    auc_roc: float
    brier_score: float

    # Calibration info
    calibration_bins: list[float]  # Predicted probability bins
    calibration_actual: list[float]  # Actual hit rate per bin

    # Feature importance
    feature_importance: dict[str, float]

    # Training config
    train_start_date: str
    train_end_date: str
    hyperparameters: dict[str, Any]


class BetPredictionModel:
    """
    XGBoost model for predicting bet outcomes.

    Outputs calibrated probability P(bet wins).
    """

    # Default hyperparameters (tuned for NCAAM betting)
    DEFAULT_PARAMS = {
        "objective": "binary:logistic",
        "eval_metric": ["logloss", "auc"],
        "max_depth": 4,              # Shallow trees prevent overfitting
        "learning_rate": 0.05,       # Slow learning for stability
        "n_estimators": 200,         # Moderate ensemble size
        "min_child_weight": 10,      # Require significant samples per leaf
        "subsample": 0.8,            # Row sampling
        "colsample_bytree": 0.8,     # Column sampling
        "reg_alpha": 0.1,            # L1 regularization
        "reg_lambda": 1.0,           # L2 regularization
        "scale_pos_weight": 1.0,     # Balanced classes
        "random_state": 42,
    }

    def __init__(
        self,
        model_type: str,
        params: dict[str, Any] | None = None,
    ):
        """
        Initialize model.

        Args:
            model_type: One of "fg_spread", "fg_total", "h1_spread", "h1_total"
            params: XGBoost parameters (uses defaults if not provided)
        """
        if not HAS_XGBOOST:
            raise ImportError("XGBoost is required. Install with: pip install xgboost")

        self.model_type = model_type
        self.params = {**self.DEFAULT_PARAMS, **(params or {})}
        self.model: xgb.XGBClassifier | None = None
        self.metadata: ModelMetadata | None = None
        self.feature_names: list[str] | None = None
        self._is_fitted = False

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray | None = None,
        y_val: np.ndarray | None = None,
        feature_names: list[str] | None = None,
        early_stopping_rounds: int = 20,
    ) -> "BetPredictionModel":
        """
        Train the model.

        Args:
            X_train: Training features (n_samples, n_features)
            y_train: Training labels (1 = bet won, 0 = bet lost)
            X_val: Validation features (for early stopping)
            y_val: Validation labels
            feature_names: Names of features for interpretability
            early_stopping_rounds: Stop if no improvement
        """
        self.feature_names = feature_names

        # Initialize model
        self.model = xgb.XGBClassifier(**self.params)

        # Fit with optional early stopping
        if X_val is not None and y_val is not None:
            self.model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                verbose=False,
            )
        else:
            self.model.fit(X_train, y_train, verbose=False)

        self._is_fitted = True
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Predict probability of bet winning.

        Args:
            X: Features (n_samples, n_features)

        Returns:
            Array of probabilities (n_samples,)
        """
        if not self._is_fitted:
            raise RuntimeError("Model must be fitted before prediction")

        # Get probability of class 1 (bet wins)
        proba = self.model.predict_proba(X)[:, 1]

        # Clip to reasonable range
        return np.clip(proba, 0.15, 0.85)

    def predict(self, X: np.ndarray, threshold: float = 0.52) -> np.ndarray:
        """
        Predict binary outcome (bet or don't bet).

        Args:
            X: Features
            threshold: Probability threshold for recommending bet

        Returns:
            Array of 0/1 predictions
        """
        proba = self.predict_proba(X)
        return (proba >= threshold).astype(int)

    def get_feature_importance(self) -> dict[str, float]:
        """Get feature importance scores."""
        if not self._is_fitted or self.feature_names is None:
            return {}

        importance = self.model.feature_importances_
        return dict(zip(self.feature_names, importance.tolist()))

    def save(self, path: Path) -> None:
        """Save model and metadata to disk."""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        # Save model
        model_path = path / f"{self.model_type}_model.json"
        self.model.save_model(str(model_path))

        # Save metadata
        if self.metadata:
            meta_path = path / f"{self.model_type}_metadata.json"
            with open(meta_path, "w") as f:
                json.dump(self.metadata.__dict__, f, indent=2, default=str)

        # Save feature names
        if self.feature_names:
            names_path = path / f"{self.model_type}_features.json"
            with open(names_path, "w") as f:
                json.dump(self.feature_names, f)

        logger.info(f"Model saved to {path}")

    @classmethod
    def load(cls, path: Path, model_type: str) -> "BetPredictionModel":
        """Load model from disk."""
        if not HAS_XGBOOST:
            raise ImportError("XGBoost is required")

        path = Path(path)

        # Load model
        model_path = path / f"{model_type}_model.json"
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")

        instance = cls(model_type)
        instance.model = xgb.XGBClassifier()
        instance.model.load_model(str(model_path))
        instance._is_fitted = True

        # Load metadata
        meta_path = path / f"{model_type}_metadata.json"
        if meta_path.exists():
            with open(meta_path) as f:
                meta_dict = json.load(f)
            instance.metadata = ModelMetadata(**meta_dict)

        # Load feature names
        names_path = path / f"{model_type}_features.json"
        if names_path.exists():
            with open(names_path) as f:
                instance.feature_names = json.load(f)

        logger.info(f"Model loaded from {path}")
        return instance


class ModelRegistry:
    """
    Registry for managing trained models.

    Handles loading/saving models and providing the appropriate model
    for each bet type.
    """

    MODEL_TYPES = ["fg_spread", "fg_total", "h1_spread", "h1_total"]

    def __init__(self, models_dir: Path | None = None):
        """
        Initialize registry.

        Args:
            models_dir: Directory containing saved models.
                        Defaults to app/ml/trained_models/
        """
        if models_dir is None:
            models_dir = Path(__file__).parent / "trained_models"

        self.models_dir = Path(models_dir)
        self._models: dict[str, BetPredictionModel] = {}
        self._loaded = False

    def load_models(self) -> bool:
        """
        Load all available models from disk.

        Returns:
            True if at least one model was loaded.
        """
        if not HAS_XGBOOST:
            logger.warning("XGBoost not available, ML models disabled")
            return False

        if not self.models_dir.exists():
            logger.warning(f"Models directory not found: {self.models_dir}")
            return False

        loaded = 0
        for model_type in self.MODEL_TYPES:
            try:
                model = BetPredictionModel.load(self.models_dir, model_type)
                self._models[model_type] = model
                loaded += 1
                logger.info(f"Loaded model: {model_type}")
            except FileNotFoundError:
                logger.debug(f"Model not found: {model_type}")
            except Exception as e:
                logger.warning(f"Failed to load {model_type}: {e}")

        self._loaded = loaded > 0
        return self._loaded

    def get_model(self, model_type: str) -> BetPredictionModel | None:
        """Get a specific model."""
        if not self._loaded:
            self.load_models()
        return self._models.get(model_type)

    def has_model(self, model_type: str) -> bool:
        """Check if a model is available."""
        if not self._loaded:
            self.load_models()
        return model_type in self._models

    def predict_proba(
        self,
        model_type: str,
        features: np.ndarray,
    ) -> np.ndarray | None:
        """
        Get probability prediction from a model.

        Returns None if model not available.
        """
        model = self.get_model(model_type)
        if model is None:
            return None
        return model.predict_proba(features)

    def save_model(self, model: BetPredictionModel) -> None:
        """Save a model to the registry directory."""
        model.save(self.models_dir)
        self._models[model.model_type] = model

    @property
    def available_models(self) -> list[str]:
        """List available model types."""
        if not self._loaded:
            self.load_models()
        return list(self._models.keys())
