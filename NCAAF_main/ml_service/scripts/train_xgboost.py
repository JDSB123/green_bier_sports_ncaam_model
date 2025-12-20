#!/usr/bin/env python3
"""
XGBoost Model Training Script for NCAAF Predictions

Trains models on historical game data to predict:
- Margin (point spread)
- Total points
- Individual team scores

Includes cross-validation, feature importance analysis, and model persistence.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import xgboost as xgb
import logging
from datetime import datetime

from src.config.settings import Settings
from src.db.database import Database
from src.features.feature_extractor import FeatureExtractor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ModelTrainer:
    """Trains XGBoost models for NCAAF predictions."""

    def __init__(self, db: Database, model_dir: str = "/app/models"):
        """
        Initialize model trainer.

        Args:
            db: Database connection
            model_dir: Directory to save trained models
        """
        self.db = db
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        self.feature_extractor = FeatureExtractor(db)
        self.models = {}
        self.feature_columns = []

    def prepare_training_data(
        self,
        start_season: int = 2018,
        end_season: int = 2024
    ) -> pd.DataFrame:
        """
        Fetch and prepare historical game data for training.

        Args:
            start_season: First season to include
            end_season: Last season to include

        Returns:
            DataFrame with features and targets
        """
        logger.info(f"Fetching historical games ({start_season}-{end_season})...")

        # Fetch completed games (Final or F/OT for overtime games)
        query = """
            SELECT
                g.id,
                g.game_id,
                g.season,
                g.week,
                g.home_team_id,
                g.away_team_id,
                g.home_score,
                g.away_score,
                g.total_score,
                g.margin
            FROM games g
            WHERE g.status IN ('Final', 'F/OT')
              AND g.season >= %s
              AND g.season <= %s
              AND g.home_score IS NOT NULL
              AND g.away_score IS NOT NULL
            ORDER BY g.season, g.week
        """

        games = self.db.fetch_all(query, (start_season, end_season))
        logger.info(f"Found {len(games)} completed games")

        # Extract features for each game
        data = []
        for game in games:
            try:
                features = self.feature_extractor.extract_game_features(
                    home_team_id=game['home_team_id'],
                    away_team_id=game['away_team_id'],
                    season=game['season'],
                    week=game['week']
                )

                # Add targets
                features['target_margin'] = float(game['margin'] or 0)
                features['target_total'] = float(game['total_score'] or 0)
                features['target_home_score'] = float(game['home_score'] or 0)
                features['target_away_score'] = float(game['away_score'] or 0)
                features['season'] = game['season']
                features['week'] = game['week']
                features['game_id'] = game['game_id']

                data.append(features)

            except Exception as e:
                logger.warning(f"Failed to extract features for game {game['game_id']}: {e}")
                continue

        df = pd.DataFrame(data)
        logger.info(f"Extracted features for {len(df)} games")
        logger.info(f"Feature dimensions: {df.shape}")

        return df

    def train_models(self, df: pd.DataFrame):
        """
        Train all XGBoost models.

        Args:
            df: DataFrame with features and targets
        """
        # Define feature columns (exclude metadata and targets)
        exclude_cols = ['target_margin', 'target_total', 'target_home_score',
                       'target_away_score', 'season', 'week', 'game_id']
        self.feature_columns = [col for col in df.columns if col not in exclude_cols]

        logger.info(f"Training with {len(self.feature_columns)} features")

        # Prepare feature matrix
        X = df[self.feature_columns].fillna(0)

        # Train margin model
        logger.info("\n" + "="*50)
        logger.info("Training Margin (Spread) Model")
        logger.info("="*50)
        y_margin = df['target_margin']
        self.models['margin'] = self._train_model(
            X, y_margin,
            model_name='margin',
            params={
                'objective': 'reg:squarederror',
                'max_depth': 6,
                'learning_rate': 0.05,
                'n_estimators': 500,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'random_state': 42
            }
        )

        # Train total model
        logger.info("\n" + "="*50)
        logger.info("Training Total Points Model")
        logger.info("="*50)
        y_total = df['target_total']
        self.models['total'] = self._train_model(
            X, y_total,
            model_name='total',
            params={
                'objective': 'reg:squarederror',
                'max_depth': 5,
                'learning_rate': 0.05,
                'n_estimators': 500,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'random_state': 42
            }
        )

        # Train home score model
        logger.info("\n" + "="*50)
        logger.info("Training Home Score Model")
        logger.info("="*50)
        y_home = df['target_home_score']
        self.models['home_score'] = self._train_model(
            X, y_home,
            model_name='home_score',
            params={
                'objective': 'reg:squarederror',
                'max_depth': 5,
                'learning_rate': 0.05,
                'n_estimators': 10,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'random_state': 42
            }
        )

        # Train away score model
        logger.info("\n" + "="*50)
        logger.info("Training Away Score Model")
        logger.info("="*50)
        y_away = df['target_away_score']
        self.models['away_score'] = self._train_model(
            X, y_away,
            model_name='away_score',
            params={
                'objective': 'reg:squarederror',
                'max_depth': 5,
                'learning_rate': 0.05,
                'n_estimators': 10,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'random_state': 42
            }
        )

    def _train_model(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        model_name: str,
        params: dict
    ) -> xgb.XGBRegressor:
        """
        Train a single XGBoost model with validation.

        Args:
            X: Feature matrix
            y: Target variable
            model_name: Name of the model
            params: XGBoost parameters

        Returns:
            Trained XGBoost model
        """
        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        logger.info(f"Training set: {len(X_train)} samples")
        logger.info(f"Test set: {len(X_test)} samples")

        # Create and train model
        model = xgb.XGBRegressor(**params)
        model.fit(
            X_train, y_train,
            verbose=True
        )

        # Evaluate
        train_pred = model.predict(X_train)
        test_pred = model.predict(X_test)

        train_mae = mean_absolute_error(y_train, train_pred)
        test_mae = mean_absolute_error(y_test, test_pred)
        train_rmse = np.sqrt(mean_squared_error(y_train, train_pred))
        test_rmse = np.sqrt(mean_squared_error(y_test, test_pred))
        train_r2 = r2_score(y_train, train_pred)
        test_r2 = r2_score(y_test, test_pred)

        logger.info(f"\nModel Performance - {model_name}:")
        logger.info(f"  Train MAE: {train_mae:.3f}, Test MAE: {test_mae:.3f}")
        logger.info(f"  Train RMSE: {train_rmse:.3f}, Test RMSE: {test_rmse:.3f}")
        logger.info(f"  Train R²: {train_r2:.3f}, Test R²: {test_r2:.3f}")

        # Cross-validation
        cv_scores = cross_val_score(
            model, X, y,
            cv=5,
            scoring='neg_mean_absolute_error',
            n_jobs=-1
        )
        logger.info(f"  5-Fold CV MAE: {-cv_scores.mean():.3f} (+/- {cv_scores.std():.3f})")

        # Feature importance
        self._log_feature_importance(model, X.columns, model_name, top_n=10)

        return model

    def _log_feature_importance(
        self,
        model: xgb.XGBRegressor,
        feature_names: list,
        model_name: str,
        top_n: int = 10
    ):
        """Log top N most important features."""
        importance_df = pd.DataFrame({
            'feature': feature_names,
            'importance': model.feature_importances_
        }).sort_values('importance', ascending=False)

        logger.info(f"\nTop {top_n} Features for {model_name}:")
        for idx, row in importance_df.head(top_n).iterrows():
            logger.info(f"  {row['feature']}: {row['importance']:.4f}")

    def save_models(self):
        """Save all trained models and feature columns to disk."""
        logger.info("\nSaving models...")

        for model_name, model in self.models.items():
            model_path = self.model_dir / f'xgboost_{model_name}.pkl'
            joblib.dump(model, model_path)
            logger.info(f"  Saved {model_name} model to {model_path}")

        # Save feature columns
        feature_path = self.model_dir / 'feature_columns.pkl'
        joblib.dump(self.feature_columns, feature_path)
        logger.info(f"  Saved feature columns to {feature_path}")

        # Save metadata
        metadata = {
            'trained_at': datetime.now().isoformat(),
            'num_features': len(self.feature_columns),
            'models': list(self.models.keys()),
        }
        metadata_path = self.model_dir / 'metadata.pkl'
        joblib.dump(metadata, metadata_path)
        logger.info(f"  Saved metadata to {metadata_path}")

        logger.info("\nAll models saved successfully!")


def main():
    """Main training pipeline."""
    logger.info("="*60)
    logger.info("NCAAF XGBoost Model Training")
    logger.info("="*60)

    # Load configuration
    settings = Settings()

    # Initialize database
    db = Database()
    db.connect()

    try:
        # Initialize trainer
        trainer = ModelTrainer(db, model_dir=settings.model_path)

        # Prepare training data
        df = trainer.prepare_training_data(
            start_season=2018,
            end_season=2024
        )

        if len(df) < 100:
            logger.error("Insufficient training data. Need at least 100 games.")
            return

        # Train models
        trainer.train_models(df)

        # Save models
        trainer.save_models()

        logger.info("\n" + "="*60)
        logger.info("Training Complete!")
        logger.info("="*60)

    except Exception as e:
        logger.error(f"Training failed: {e}", exc_info=True)
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
