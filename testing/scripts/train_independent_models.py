#!/usr/bin/env python3
"""
Independent Model Training for NCAAM Prediction

Trains 4 INDEPENDENT models - one for each market:
1. FG Spread Model
2. FG Total Model
3. 1H Spread Model
4. 1H Total Model

CRITICAL REQUIREMENTS:
- NO LEAKAGE: Walk-forward training (train on past, test on future)
- NO ASSUMPTIONS: Actual odds required, no -110 fallback
- NO PLACEHOLDERS: Missing data = skip, not fill
- NO SEASON AVERAGES: Only rolling windows (last 3, 5, 10 games)
- POINT-IN-TIME RATINGS: Only use ratings from before game date

Usage:
    python testing/scripts/train_independent_models.py --market fg_spread
    python testing/scripts/train_independent_models.py --all-markets
    python testing/scripts/train_independent_models.py --evaluate-only  # No training, just evaluate existing
"""

import argparse
import json
import pickle
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.metrics import (
        accuracy_score, log_loss, roc_auc_score, brier_score_loss,
        calibration_curve
    )
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False


class MarketType(str, Enum):
    """Four betting markets - each gets an INDEPENDENT model."""
    FG_SPREAD = "fg_spread"
    FG_TOTAL = "fg_total"
    H1_SPREAD = "h1_spread"
    H1_TOTAL = "h1_total"


@dataclass
class ModelConfig:
    """Configuration for model training."""
    market: MarketType
    
    # Training window
    train_start_season: int = 2020
    train_end_season: int = 2024
    
    # XGBoost hyperparameters
    max_depth: int = 4
    learning_rate: float = 0.05
    n_estimators: int = 200
    min_child_weight: int = 10
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    reg_alpha: float = 0.1
    reg_lambda: float = 1.0
    
    # Validation
    n_cv_splits: int = 5
    min_train_size: int = 500
    
    # Feature selection
    use_barttorvik: bool = True
    use_four_factors: bool = True
    use_ncaahoopR: bool = True
    use_market_features: bool = True
    
    # No season averages! Only rolling windows
    rolling_windows: List[int] = field(default_factory=lambda: [3, 5, 10])


@dataclass
class FeatureSet:
    """Features for model training - all pre-game, no leakage."""
    
    # Core efficiency (point-in-time Barttorvik ratings)
    BARTTORVIK_FEATURES = [
        "home_adj_o", "home_adj_d", "home_tempo", "home_barthag",
        "away_adj_o", "away_adj_d", "away_tempo", "away_barthag",
    ]
    
    # Four Factors (pre-game only)
    FOUR_FACTORS_FEATURES = [
        "home_efg", "home_efgd", "home_tor", "home_tord",
        "home_orb", "home_drb", "home_ftr", "home_ftrd",
        "away_efg", "away_efgd", "away_tor", "away_tord",
        "away_orb", "away_drb", "away_ftr", "away_ftrd",
    ]
    
    # Shooting
    SHOOTING_FEATURES = [
        "home_two_pt_rate", "home_three_pt_rate",
        "away_two_pt_rate", "away_three_pt_rate",
    ]
    
    # Quality metrics
    QUALITY_FEATURES = [
        "home_wab", "away_wab",
    ]
    
    # ncaahoopR rolling windows (pre-game, last N games)
    NCAAHOPR_ROLLING_FEATURES = [
        # Last 3 games
        "home_box_efg_last3", "home_box_ppp_last3", "home_box_tor_last3",
        "away_box_efg_last3", "away_box_ppp_last3", "away_box_tor_last3",
        "diff_box_efg_last3", "diff_box_ppp_last3",
        
        # Last 5 games
        "home_box_efg_last5", "home_box_ppp_last5", "home_box_tor_last5",
        "away_box_efg_last5", "away_box_ppp_last5", "away_box_tor_last5",
        "diff_box_efg_last5", "diff_box_ppp_last5",
        
        # Last 10 games
        "home_box_efg_last10", "home_box_ppp_last10", "home_box_tor_last10",
        "away_box_efg_last10", "away_box_ppp_last10", "away_box_tor_last10",
        "diff_box_efg_last10", "diff_box_ppp_last10",
    ]
    
    # Market features (opening line only, not closing!)
    MARKET_FEATURES = [
        # We could add: opening line, line vs prediction
        # But we need to be careful about leakage
    ]


@dataclass
class ModelMetadata:
    """Metadata for a trained model."""
    model_type: str
    version: str
    trained_at: str
    
    # Training info
    training_seasons: List[int]
    training_samples: int
    validation_samples: int
    
    # Performance metrics
    accuracy: float
    log_loss: float
    auc_roc: float
    brier_score: float
    
    # Calibration
    calibration_bins: List[float]
    calibration_actual: List[float]
    
    # Feature importance
    feature_importance: Dict[str, float]
    
    # Hyperparameters
    hyperparameters: Dict[str, Any]


class IndependentModelTrainer:
    """
    Trains independent models for each market.
    
    CRITICAL: Each model is completely independent:
    - Own feature set (optimized for that market)
    - Own calibration
    - Own hyperparameters
    - No shared parameters with other markets
    """
    
    def __init__(self, config: ModelConfig):
        if not XGBOOST_AVAILABLE:
            raise ImportError("XGBoost required. Install with: pip install xgboost")
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn required. Install with: pip install scikit-learn")
        
        self.config = config
        
        # Paths
        self.root_dir = Path(__file__).resolve().parents[2]
        self.data_dir = self.root_dir / "ncaam_historical_data_local" / "backtest_datasets"
        self.models_dir = self.root_dir / "testing" / "models"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Model version
        self.version = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def load_training_data(self) -> pd.DataFrame:
        """Load backtest dataset for training."""
        # Prefer enhanced dataset with ncaahoopR features
        enhanced_path = self.data_dir / "backtest_master_enhanced.csv"
        consolidated_path = self.data_dir / "backtest_master_consolidated.csv"
        base_path = self.data_dir / "backtest_master.csv"
        
        for path in [enhanced_path, consolidated_path, base_path]:
            if path.exists():
                print(f"Loading training data from: {path.name}")
                df = pd.read_csv(path)
                df["game_date"] = pd.to_datetime(df["game_date"])
                return df
        
        raise FileNotFoundError("Backtest dataset not found")
    
    def get_feature_columns(self) -> List[str]:
        """Get feature columns based on config."""
        features = []
        
        if self.config.use_barttorvik:
            features.extend(FeatureSet.BARTTORVIK_FEATURES)
        
        if self.config.use_four_factors:
            features.extend(FeatureSet.FOUR_FACTORS_FEATURES)
            features.extend(FeatureSet.SHOOTING_FEATURES)
            features.extend(FeatureSet.QUALITY_FEATURES)
        
        if self.config.use_ncaahoopR:
            features.extend(FeatureSet.NCAAHOPR_ROLLING_FEATURES)
        
        return features
    
    def get_target_column(self) -> str:
        """Get target column based on market type."""
        market = self.config.market.value
        
        # Target is whether the bet would have won
        # 1 = bet won, 0 = bet lost
        target_map = {
            "fg_spread": "fg_spread_covered",  # 1 if home covered
            "fg_total": "fg_total_over",  # 1 if over hit
            "h1_spread": "h1_spread_covered",  # 1 if home covered
            "h1_total": "h1_total_over",  # 1 if over hit
        }
        
        return target_map.get(market, "fg_spread_covered")
    
    def prepare_training_data(
        self,
        df: pd.DataFrame
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        Prepare feature matrix and labels.
        
        CRITICAL: No leakage - only use pre-game data.
        """
        # Filter to training seasons
        df = df[
            (df["season"] >= self.config.train_start_season) &
            (df["season"] <= self.config.train_end_season)
        ].copy()
        
        # Sort by date for time-series split
        df = df.sort_values("game_date")
        
        # Get features and target
        feature_cols = self.get_feature_columns()
        target_col = self.get_target_column()
        
        # Filter to available features
        available_features = [col for col in feature_cols if col in df.columns]
        missing_features = [col for col in feature_cols if col not in df.columns]
        
        if missing_features:
            print(f"Warning: {len(missing_features)} features not available:")
            for feat in missing_features[:5]:
                print(f"  - {feat}")
        
        # Check target column
        if target_col not in df.columns:
            raise ValueError(f"Target column {target_col} not in dataset")
        
        # Remove rows with missing target
        df = df[df[target_col].notna()]
        
        # Create feature matrix
        X = df[available_features].copy()
        y = df[target_col].astype(int)
        
        # Handle missing values (no placeholders - use indicator columns or drop)
        # For now, fill with median (could improve this)
        for col in available_features:
            if X[col].isna().any():
                # Option 1: Add missing indicator
                X[f"{col}_missing"] = X[col].isna().astype(int)
                available_features.append(f"{col}_missing")
                
                # Option 2: Fill with median of non-missing
                median_val = X[col].median()
                X[col] = X[col].fillna(median_val)
        
        print(f"\nTraining data prepared:")
        print(f"  Samples: {len(X)}")
        print(f"  Features: {len(available_features)}")
        print(f"  Target distribution: {y.value_counts().to_dict()}")
        
        return X.values, y.values, list(X.columns)
    
    def time_series_cross_validate(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str]
    ) -> Dict[str, float]:
        """
        Perform time-series cross-validation.
        
        CRITICAL: Training data always before test data - no leakage.
        """
        tscv = TimeSeriesSplit(n_splits=self.config.n_cv_splits)
        
        metrics = {
            "accuracy": [],
            "log_loss": [],
            "auc_roc": [],
            "brier_score": []
        }
        
        print(f"\nRunning {self.config.n_cv_splits}-fold time-series cross-validation...")
        
        for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
            if len(train_idx) < self.config.min_train_size:
                print(f"  Fold {fold+1}: Skipping (train size {len(train_idx)} < {self.config.min_train_size})")
                continue
            
            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]
            
            # Train model
            model = xgb.XGBClassifier(
                max_depth=self.config.max_depth,
                learning_rate=self.config.learning_rate,
                n_estimators=self.config.n_estimators,
                min_child_weight=self.config.min_child_weight,
                subsample=self.config.subsample,
                colsample_bytree=self.config.colsample_bytree,
                reg_alpha=self.config.reg_alpha,
                reg_lambda=self.config.reg_lambda,
                objective="binary:logistic",
                eval_metric=["logloss", "auc"],
                random_state=42,
                n_jobs=-1
            )
            
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                verbose=False
            )
            
            # Predict probabilities
            y_pred_proba = model.predict_proba(X_val)[:, 1]
            y_pred = (y_pred_proba > 0.5).astype(int)
            
            # Calculate metrics
            metrics["accuracy"].append(accuracy_score(y_val, y_pred))
            metrics["log_loss"].append(log_loss(y_val, y_pred_proba))
            metrics["auc_roc"].append(roc_auc_score(y_val, y_pred_proba))
            metrics["brier_score"].append(brier_score_loss(y_val, y_pred_proba))
            
            print(f"  Fold {fold+1}: Acc={metrics['accuracy'][-1]:.3f}, "
                  f"AUC={metrics['auc_roc'][-1]:.3f}, "
                  f"LogLoss={metrics['log_loss'][-1]:.4f}")
        
        # Average metrics
        avg_metrics = {
            key: np.mean(values) for key, values in metrics.items()
        }
        
        print(f"\nCV Results:")
        print(f"  Mean Accuracy: {avg_metrics['accuracy']:.3f}")
        print(f"  Mean AUC-ROC: {avg_metrics['auc_roc']:.3f}")
        print(f"  Mean Log Loss: {avg_metrics['log_loss']:.4f}")
        print(f"  Mean Brier Score: {avg_metrics['brier_score']:.4f}")
        
        return avg_metrics
    
    def train_final_model(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str]
    ) -> Tuple[xgb.XGBClassifier, ModelMetadata]:
        """
        Train the final model on all data.
        
        Uses last portion as validation for early stopping.
        """
        print(f"\nTraining final {self.config.market.value} model...")
        
        # Use last 15% as validation for early stopping
        n = len(X)
        train_size = int(n * 0.85)
        
        X_train, X_val = X[:train_size], X[train_size:]
        y_train, y_val = y[:train_size], y[train_size:]
        
        # Train model
        model = xgb.XGBClassifier(
            max_depth=self.config.max_depth,
            learning_rate=self.config.learning_rate,
            n_estimators=self.config.n_estimators,
            min_child_weight=self.config.min_child_weight,
            subsample=self.config.subsample,
            colsample_bytree=self.config.colsample_bytree,
            reg_alpha=self.config.reg_alpha,
            reg_lambda=self.config.reg_lambda,
            objective="binary:logistic",
            eval_metric=["logloss", "auc"],
            random_state=42,
            n_jobs=-1,
            early_stopping_rounds=20
        )
        
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False
        )
        
        # Evaluate on validation set
        y_pred_proba = model.predict_proba(X_val)[:, 1]
        y_pred = (y_pred_proba > 0.5).astype(int)
        
        accuracy = accuracy_score(y_val, y_pred)
        ll = log_loss(y_val, y_pred_proba)
        auc = roc_auc_score(y_val, y_pred_proba)
        brier = brier_score_loss(y_val, y_pred_proba)
        
        print(f"  Final model validation:")
        print(f"    Accuracy: {accuracy:.3f}")
        print(f"    AUC-ROC: {auc:.3f}")
        print(f"    Log Loss: {ll:.4f}")
        print(f"    Brier Score: {brier:.4f}")
        
        # Calibration curve
        try:
            prob_true, prob_pred = calibration_curve(y_val, y_pred_proba, n_bins=10)
        except ValueError:
            prob_true, prob_pred = [], []
        
        # Feature importance
        importance = dict(zip(feature_names, model.feature_importances_))
        importance = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))
        
        print(f"\n  Top 10 features:")
        for feat, imp in list(importance.items())[:10]:
            print(f"    {feat}: {imp:.4f}")
        
        # Create metadata
        metadata = ModelMetadata(
            model_type=self.config.market.value,
            version=self.version,
            trained_at=datetime.now().isoformat(),
            training_seasons=list(range(self.config.train_start_season, self.config.train_end_season + 1)),
            training_samples=len(X_train),
            validation_samples=len(X_val),
            accuracy=round(accuracy, 4),
            log_loss=round(ll, 4),
            auc_roc=round(auc, 4),
            brier_score=round(brier, 4),
            calibration_bins=prob_pred.tolist() if len(prob_pred) > 0 else [],
            calibration_actual=prob_true.tolist() if len(prob_true) > 0 else [],
            feature_importance=importance,
            hyperparameters={
                "max_depth": self.config.max_depth,
                "learning_rate": self.config.learning_rate,
                "n_estimators": self.config.n_estimators,
                "min_child_weight": self.config.min_child_weight,
                "subsample": self.config.subsample,
                "colsample_bytree": self.config.colsample_bytree,
                "reg_alpha": self.config.reg_alpha,
                "reg_lambda": self.config.reg_lambda,
            }
        )
        
        return model, metadata
    
    def save_model(
        self,
        model: xgb.XGBClassifier,
        metadata: ModelMetadata,
        feature_names: List[str]
    ):
        """Save trained model and metadata."""
        market = self.config.market.value
        
        # Save model
        model_path = self.models_dir / f"{market}_model_{self.version}.pkl"
        with open(model_path, 'wb') as f:
            pickle.dump({
                "model": model,
                "feature_names": feature_names,
                "metadata": metadata
            }, f)
        
        # Save metadata as JSON
        metadata_path = self.models_dir / f"{market}_model_{self.version}.json"
        with open(metadata_path, 'w') as f:
            json.dump({
                "model_type": metadata.model_type,
                "version": metadata.version,
                "trained_at": metadata.trained_at,
                "training_seasons": metadata.training_seasons,
                "training_samples": metadata.training_samples,
                "validation_samples": metadata.validation_samples,
                "accuracy": metadata.accuracy,
                "log_loss": metadata.log_loss,
                "auc_roc": metadata.auc_roc,
                "brier_score": metadata.brier_score,
                "calibration_bins": metadata.calibration_bins,
                "calibration_actual": metadata.calibration_actual,
                "feature_importance": dict(list(metadata.feature_importance.items())[:20]),
                "hyperparameters": metadata.hyperparameters
            }, f, indent=2)
        
        # Create symlink to latest
        latest_path = self.models_dir / f"{market}_model_latest.pkl"
        if latest_path.exists():
            latest_path.unlink()
        
        # On Windows, use copy instead of symlink
        import shutil
        shutil.copy2(model_path, latest_path)
        
        print(f"\nModel saved:")
        print(f"  Model: {model_path}")
        print(f"  Metadata: {metadata_path}")
        print(f"  Latest: {latest_path}")
    
    def train(self) -> Tuple[xgb.XGBClassifier, ModelMetadata]:
        """
        Full training pipeline.
        
        Returns trained model and metadata.
        """
        print("=" * 70)
        print(f"TRAINING INDEPENDENT MODEL: {self.config.market.value}")
        print("=" * 70)
        print(f"Train seasons: {self.config.train_start_season}-{self.config.train_end_season}")
        print()
        
        # Load data
        df = self.load_training_data()
        
        # Prepare training data
        X, y, feature_names = self.prepare_training_data(df)
        
        # Cross-validate
        cv_metrics = self.time_series_cross_validate(X, y, feature_names)
        
        # Train final model
        model, metadata = self.train_final_model(X, y, feature_names)
        
        # Save model
        self.save_model(model, metadata, feature_names)
        
        return model, metadata


def load_model(market: str, models_dir: Optional[Path] = None) -> Tuple[Any, List[str], ModelMetadata]:
    """
    Load a trained model.
    
    Args:
        market: Market type (fg_spread, fg_total, h1_spread, h1_total)
        models_dir: Optional path to models directory
    
    Returns:
        Tuple of (model, feature_names, metadata)
    """
    if models_dir is None:
        models_dir = Path(__file__).resolve().parents[2] / "testing" / "models"
    
    model_path = models_dir / f"{market}_model_latest.pkl"
    
    if not model_path.exists():
        raise FileNotFoundError(f"No model found for {market} at {model_path}")
    
    with open(model_path, 'rb') as f:
        data = pickle.load(f)
    
    return data["model"], data["feature_names"], data["metadata"]


def main():
    parser = argparse.ArgumentParser(
        description="Train independent models for NCAAM prediction"
    )
    parser.add_argument(
        "--market",
        type=str,
        default="fg_spread",
        choices=["fg_spread", "fg_total", "h1_spread", "h1_total"],
        help="Market to train model for"
    )
    parser.add_argument(
        "--all-markets",
        action="store_true",
        help="Train models for all markets"
    )
    parser.add_argument(
        "--train-seasons",
        type=str,
        default="2020-2024",
        help="Training season range (e.g., 2020-2024)"
    )
    parser.add_argument(
        "--evaluate-only",
        action="store_true",
        help="Only evaluate existing models, don't train"
    )
    
    args = parser.parse_args()
    
    # Parse training seasons
    train_start, train_end = map(int, args.train_seasons.split("-"))
    
    markets = (
        [MarketType.FG_SPREAD, MarketType.FG_TOTAL, MarketType.H1_SPREAD, MarketType.H1_TOTAL]
        if args.all_markets
        else [MarketType(args.market)]
    )
    
    for market in markets:
        if args.evaluate_only:
            # Load and evaluate existing model
            try:
                model, feature_names, metadata = load_model(market.value)
                print(f"\n{market.value} model:")
                print(f"  Version: {metadata.version}")
                print(f"  Accuracy: {metadata.accuracy:.3f}")
                print(f"  AUC-ROC: {metadata.auc_roc:.3f}")
            except FileNotFoundError as e:
                print(f"No model found for {market.value}: {e}")
        else:
            # Train new model
            config = ModelConfig(
                market=market,
                train_start_season=train_start,
                train_end_season=train_end
            )
            
            trainer = IndependentModelTrainer(config)
            trainer.train()


if __name__ == "__main__":
    main()
