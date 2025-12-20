"""
XGBoost Predictor for NCAAF Game Predictions

Loads trained models and generates predictions with confidence scores,
edge calculations vs market, and betting recommendations.

IMPORTANT: This predictor loads models from:
  - models/enhanced/spread_model.pkl (primary)
  - models/enhanced/total_model.pkl (primary)
  - Fallback to models/baseline/ if enhanced not found
"""

import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class NCAAFPredictor:
    """
    College football game predictor using XGBoost models.

    Generates predictions for:
    - Point spread (margin)
    - Total points (over/under)
    - Individual team scores
    - Win probability

    Calculates edge vs market consensus and generates betting recommendations.
    """

    def __init__(self, model_dir: str = "/app/models"):
        """
        Initialize predictor with trained models.

        Args:
            model_dir: Directory containing trained model files
        """
        self.model_dir = Path(model_dir)
        self.models = {}
        self.feature_columns = []
        self._load_models()

    def _load_models(self):
        """
        Load all trained models from disk.
        
        Model loading priority:
        1. models/enhanced/spread_model.pkl, total_model.pkl (primary)
        2. models/baseline/spread_model.pkl, total_model.pkl (fallback)
        3. models/xgboost_margin.pkl, xgboost_total.pkl (legacy)
        """
        # Define model search paths in priority order
        model_paths = [
            # Enhanced models (primary)
            {
                'margin': self.model_dir / 'enhanced' / 'spread_model.pkl',
                'total': self.model_dir / 'enhanced' / 'total_model.pkl',
                'features': self.model_dir / 'enhanced' / 'feature_names.pkl',
            },
            # Baseline models (fallback)
            {
                'margin': self.model_dir / 'baseline' / 'spread_model.pkl',
                'total': self.model_dir / 'baseline' / 'total_model.pkl',
                'features': self.model_dir / 'baseline' / 'feature_names.pkl',
            },
            # Legacy model names (backward compatibility)
            {
                'margin': self.model_dir / 'xgboost_margin.pkl',
                'total': self.model_dir / 'xgboost_total.pkl',
                'features': self.model_dir / 'feature_columns.pkl',
            },
        ]
        
        models_loaded = False
        
        for paths in model_paths:
            if paths['margin'].exists() and paths['total'].exists():
                try:
                    self.models['margin'] = joblib.load(paths['margin'])
                    self.models['total'] = joblib.load(paths['total'])
                    logger.info(f"Loaded spread model from: {paths['margin']}")
                    logger.info(f"Loaded total model from: {paths['total']}")
                    
                    # Load feature columns
                    if paths['features'].exists():
                        self.feature_columns = joblib.load(paths['features'])
                        logger.info(f"Loaded {len(self.feature_columns)} feature columns")
                    
                    models_loaded = True
                    break
                except Exception as e:
                    logger.error(f"Failed to load models from {paths['margin'].parent}: {e}")
                    continue
        
        if not models_loaded:
            logger.warning("No trained models found! Run 'run.bat train' to train models.")
            # Set None for missing models
            self.models['margin'] = None
            self.models['total'] = None

    def predict_game(
        self,
        features: Dict[str, float],
        consensus_spread: Optional[float] = None,
        consensus_total: Optional[float] = None
    ) -> Dict:
        """
        Generate full prediction for a game with input validation.
        """
        # Input validation: ensure features is a dict of str: float
        if not isinstance(features, dict):
            raise ValueError("Features must be a dictionary.")
        for k, v in features.items():
            if not isinstance(k, str):
                raise ValueError(f"Feature key {k} is not a string.")
            if not isinstance(v, (float, int)):
                raise ValueError(f"Feature value for {k} is not a number.")

        X = self._prepare_features(features)

        predictions = {}

        # Margin prediction
        if self.models.get('margin'):
            margin_pred = self.models['margin'].predict(X)[0]
            predictions['predicted_margin'] = float(margin_pred)
        else:
            predictions['predicted_margin'] = 0.0

        # Total prediction
        if self.models.get('total'):
            total_pred = self.models['total'].predict(X)[0]
            predictions['predicted_total'] = float(total_pred)
        else:
            predictions['predicted_total'] = 0.0

        # Score predictions
        if self.models.get('home_score') and self.models.get('away_score'):
            home_score_pred = self.models['home_score'].predict(X)[0]
            away_score_pred = self.models['away_score'].predict(X)[0]
            predictions['predicted_home_score'] = float(home_score_pred)
            predictions['predicted_away_score'] = float(away_score_pred)

            # Reconcile predictions (use score-based if available)
            predictions['predicted_margin'] = predictions['predicted_home_score'] - predictions['predicted_away_score']
            predictions['predicted_total'] = predictions['predicted_home_score'] + predictions['predicted_away_score']
        else:
            # Derive scores from margin and total
            predictions['predicted_home_score'] = (predictions['predicted_total'] + predictions['predicted_margin']) / 2
            predictions['predicted_away_score'] = (predictions['predicted_total'] - predictions['predicted_margin']) / 2

        predictions['confidence_score'] = self._calculate_confidence(features, predictions)

        if consensus_spread is not None:
            predictions['consensus_spread'] = float(consensus_spread)
            predictions['edge_spread'] = predictions['predicted_margin'] - consensus_spread
        else:
            predictions['consensus_spread'] = None
            predictions['edge_spread'] = None

        if consensus_total is not None:
            predictions['consensus_total'] = float(consensus_total)
            predictions['edge_total'] = predictions['predicted_total'] - consensus_total
        else:
            predictions['consensus_total'] = None
            predictions['edge_total'] = None

        recommendation = self._generate_recommendation(predictions)
        predictions.update(recommendation)

        return predictions

    def _prepare_features(self, features: Dict[str, float]) -> pd.DataFrame:
        """
        Prepare features for model prediction.

        Ensures correct column order and handles missing features.
        """
        if not self.feature_columns:
            # If no feature columns loaded, use all features
            return pd.DataFrame([features])

        # Create DataFrame with correct column order
        feature_dict = {col: features.get(col, 0.0) for col in self.feature_columns}
        return pd.DataFrame([feature_dict])

    def _calculate_confidence(
        self,
        features: Dict[str, float],
        predictions: Dict[str, float]
    ) -> float:
        """
        Calculate confidence score for predictions.

        Higher confidence when:
        - Large talent differential
        - Consistent recent form
        - Strong efficiency differentials
        - Home team has home field advantage data

        Returns:
            Confidence score between 0 and 1
        """
        confidence = 0.5  # Base confidence

        # Talent differential (0.0 - 0.2)
        talent_diff = abs(features.get('talent_differential', 0.0))
        confidence += min(talent_diff * 0.4, 0.2)

        # Efficiency differential (0.0 - 0.15)
        off_diff = abs(features.get('offensive_diff', 0.0))
        def_diff = abs(features.get('defensive_diff', 0.0))
        efficiency_factor = (off_diff + def_diff) / 10.0
        confidence += min(efficiency_factor, 0.15)

        # Recent form consistency (0.0 - 0.1)
        home_recent_margin = features.get('home_recent_margin', 0.0)
        away_recent_margin = features.get('away_recent_margin', 0.0)
        if abs(home_recent_margin) > 7.0 or abs(away_recent_margin) > 7.0:
            confidence += 0.1

        # PPG differential (0.0 - 0.1)
        ppg_diff = abs(features.get('ppg_diff', 0.0))
        confidence += min(ppg_diff / 140.0, 0.1)

        # Normalize to 0-1 range
        return min(max(confidence, 0.0), 1.0)

    def _generate_recommendation(self, predictions: Dict[str, float]) -> Dict:
        """
        Generate betting recommendation based on edge and confidence.

        Recommendation criteria:
        - Edge must exceed threshold (2-3 points for spread, 3-4 points for total)
        - Confidence must be sufficient (>0.6)
        - Recommended units scale with edge and confidence

        Returns:
            Dictionary with:
            - recommend_bet: bool
            - recommended_bet_type: str or None
            - recommended_side: str or None
            - recommended_units: float
            - rationale: dict with reasoning
        """
        recommendation = {
            'recommend_bet': False,
            'recommended_bet_type': None,
            'recommended_side': None,
            'recommended_units': 0.0,
            'rationale': {
                'key_factors': [],
                'strengths': [],
                'concerns': [],
            }
        }

        edge_spread = predictions.get('edge_spread')
        edge_total = predictions.get('edge_total')
        confidence = predictions['confidence_score']

        # Minimum thresholds
        MIN_SPREAD_EDGE = 2.5  # points
        MIN_TOTAL_EDGE = 3.5   # points
        MIN_CONFIDENCE = 0.60

        # Check spread edge
        spread_bet = None
        if edge_spread is not None:
            if edge_spread >= MIN_SPREAD_EDGE and confidence >= MIN_CONFIDENCE:
                spread_bet = {
                    'type': 'spread',
                    'side': 'home',
                    'edge': edge_spread,
                    'units': self._calculate_units(edge_spread, confidence, 'spread')
                }
                recommendation['rationale']['key_factors'].append(
                    f"Model favors home by {predictions['predicted_margin']:.1f}, market at {predictions['consensus_spread']:.1f}"
                )
            elif edge_spread <= -MIN_SPREAD_EDGE and confidence >= MIN_CONFIDENCE:
                spread_bet = {
                    'type': 'spread',
                    'side': 'away',
                    'edge': abs(edge_spread),
                    'units': self._calculate_units(abs(edge_spread), confidence, 'spread')
                }
                recommendation['rationale']['key_factors'].append(
                    f"Model favors away by {-predictions['predicted_margin']:.1f}, market at {-predictions['consensus_spread']:.1f}"
                )

        # Check total edge
        total_bet = None
        if edge_total is not None:
            if edge_total >= MIN_TOTAL_EDGE and confidence >= MIN_CONFIDENCE:
                total_bet = {
                    'type': 'total',
                    'side': 'over',
                    'edge': edge_total,
                    'units': self._calculate_units(edge_total, confidence, 'total')
                }
                recommendation['rationale']['key_factors'].append(
                    f"Model projects {predictions['predicted_total']:.1f} points, market at {predictions['consensus_total']:.1f}"
                )
            elif edge_total <= -MIN_TOTAL_EDGE and confidence >= MIN_CONFIDENCE:
                total_bet = {
                    'type': 'total',
                    'side': 'under',
                    'edge': abs(edge_total),
                    'units': self._calculate_units(abs(edge_total), confidence, 'total')
                }
                recommendation['rationale']['key_factors'].append(
                    f"Model projects {predictions['predicted_total']:.1f} points, market at {predictions['consensus_total']:.1f}"
                )

        # Select best bet (highest edge * confidence)
        best_bet = None
        if spread_bet and total_bet:
            spread_value = spread_bet['edge'] * confidence
            total_value = total_bet['edge'] * confidence
            best_bet = spread_bet if spread_value >= total_value else total_bet
        elif spread_bet:
            best_bet = spread_bet
        elif total_bet:
            best_bet = total_bet

        if best_bet:
            recommendation['recommend_bet'] = True
            recommendation['recommended_bet_type'] = best_bet['type']
            recommendation['recommended_side'] = best_bet['side']
            recommendation['recommended_units'] = best_bet['units']

            # Add strengths and concerns
            if confidence >= 0.75:
                recommendation['rationale']['strengths'].append("High confidence prediction")
            if best_bet['edge'] >= 5.0:
                recommendation['rationale']['strengths'].append("Significant edge vs market")

            if confidence < 0.70:
                recommendation['rationale']['concerns'].append("Moderate confidence level")

        return recommendation

    def _calculate_units(self, edge: float, confidence: float, bet_type: str) -> float:
        """
        Calculate recommended bet size using Kelly-inspired sizing.

        Args:
            edge: Predicted edge in points
            confidence: Confidence score (0-1)
            bet_type: 'spread' or 'total'

        Returns:
            Recommended units (0.5 - 2.0)
        """
        # Base sizing
        if bet_type == 'spread':
            base_units = min(edge / 10.0, 1.5)  # Max 1.5 units for spread
        else:
            base_units = min(edge / 12.0, 1.5)  # Slightly more conservative for totals

        # Adjust by confidence
        adjusted_units = base_units * confidence

        # Floor and ceiling
        return max(0.5, min(adjusted_units, 2.0))
